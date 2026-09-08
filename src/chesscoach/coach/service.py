"""Cancellable adaptive full-game Stockfish analysis."""

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, replace
from threading import Event
from typing import Protocol

import chess
import chess.engine

from chesscoach.coach.facts import extract_evidence
from chesscoach.coach.models import AnalysisProfile, AnalysisProgress, GameAnalysis, MoveAnalysis
from chesscoach.coach.scoring import (
    classify_move,
    engine_score,
    game_phase,
    move_accuracy,
    move_loss,
    phase_summaries,
    player_accuracy,
    turning_points,
)
from chesscoach.engine.analysis import PositionAnalysis
from chesscoach.engine.stockfish import Stockfish
from chesscoach.storage.database import GameData


class AnalysisCancelled(RuntimeError):
    pass


class AnalysisCache(Protocol):
    def get_move_analysis(self, key: str) -> MoveAnalysis | None: ...

    def put_move_analysis(self, key: str, analysis: MoveAnalysis) -> None: ...


class BatchEngine(Protocol):
    @property
    def signature(self) -> str: ...

    def analyze(
        self,
        position: chess.Board,
        *,
        limit: chess.engine.Limit,
        multipv: int = 1,
        root_moves: Sequence[chess.Move] | None = None,
        pv_plies: int | None = None,
    ) -> PositionAnalysis: ...

    def close(self) -> None: ...


ProgressCallback = Callable[[AnalysisProgress], None]
EngineFactory = Callable[[str], BatchEngine]


class GameAnalysisService:
    def __init__(
        self,
        engine_factory: EngineFactory = Stockfish,
        cache: AnalysisCache | None = None,
    ) -> None:
        self.engine_factory = engine_factory
        self.cache = cache

    def analyze(
        self,
        data: GameData,
        engine_path: str,
        profile: AnalysisProfile | None = None,
        *,
        cancelled: Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> GameAnalysis:
        data.validate()
        selected = profile or AnalysisProfile()
        selected.validate()
        stop = cancelled or Event()
        notify = progress or (lambda update: None)
        engine = self.engine_factory(engine_path)
        effective_profile = replace(selected, engine_signature=engine.signature)
        moves: list[MoveAnalysis] = []
        cached_count = 0
        try:
            board = chess.Board(data.fens[0])
            for index, uci in enumerate(data.moves):
                self._check_cancelled(stop)
                move = chess.Move.from_uci(uci)
                key = self.cache_key(board, move, effective_profile, deep=False)
                analysis = self.cache.get_move_analysis(key) if self.cache else None
                if analysis is None:
                    analysis = self._analyze_move(
                        engine, board, move, index + 1, effective_profile, deep=False
                    )
                    if self.cache:
                        self.cache.put_move_analysis(key, analysis)
                else:
                    cached_count += 1
                moves.append(analysis)
                board.push(move)
                notify(AnalysisProgress(index + 1, len(data.moves), "quick", cached_count))

            candidates = [index for index, move in enumerate(moves) if self._needs_deepening(move)]
            total = len(data.moves) + len(candidates)
            for offset, index in enumerate(candidates, start=1):
                self._check_cancelled(stop)
                board = chess.Board(moves[index].fen)
                played = chess.Move.from_uci(moves[index].played_uci)
                key = self.cache_key(board, played, effective_profile, deep=True)
                analysis = self.cache.get_move_analysis(key) if self.cache else None
                if analysis is None:
                    analysis = self._analyze_move(
                        engine, board, played, index + 1, effective_profile, deep=True
                    )
                    if self.cache:
                        self.cache.put_move_analysis(key, analysis)
                else:
                    cached_count += 1
                moves[index] = analysis
                notify(AnalysisProgress(len(data.moves) + offset, total, "deep", cached_count))
        finally:
            engine.close()
        result = tuple(moves)
        return GameAnalysis(
            data.id,
            effective_profile,
            result,
            turning_points(result),
            player_accuracy(result, data.player_color),
            phase_summaries(result, data.player_color),
        )

    @staticmethod
    def cache_key(
        board: chess.Board, move: chess.Move, profile: AnalysisProfile, *, deep: bool
    ) -> str:
        payload = {
            "fen": " ".join(board.fen().split()[:4]),
            "move": move.uci(),
            "profile": asdict(profile),
            "deep": deep,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _check_cancelled(cancelled: Event) -> None:
        if cancelled.is_set():
            raise AnalysisCancelled("Game analysis was cancelled.")

    @staticmethod
    def _needs_deepening(move: MoveAnalysis) -> bool:
        near_boundary = any(abs(move.loss_percent - boundary) <= 1 for boundary in (5, 10, 20))
        return (
            move.loss_percent >= 5
            or near_boundary
            or move.best_score.mate is not None
            or move.played_score.mate is not None
        )

    @staticmethod
    def _analyze_move(
        engine: BatchEngine,
        board: chess.Board,
        played: chess.Move,
        ply: int,
        profile: AnalysisProfile,
        *,
        deep: bool,
    ) -> MoveAnalysis:
        limit = chess.engine.Limit(time=profile.deep_time if deep else profile.quick_time)
        best_result = engine.analyze(
            board,
            limit=limit,
            multipv=profile.multipv,
            pv_plies=profile.pv_plies,
        )
        best = best_result.best_move
        if best is None:
            raise ValueError("Stockfish returned no best move for a non-terminal position.")
        if played == best:
            played_result = best_result
        else:
            played_result = engine.analyze(
                board,
                limit=limit,
                root_moves=(played,),
                pv_plies=profile.pv_plies,
            )
        best_line = best_result.candidates[0]
        played_line = played_result.candidates[0]
        best_score = engine_score(best_line.score)
        played_score = engine_score(played_line.score)
        loss = move_loss(best_score, played_score, board.turn)
        evidence = extract_evidence(board, played, best)
        return MoveAnalysis(
            ply=ply,
            fen=board.fen(),
            mover="white" if board.turn else "black",
            played_uci=played.uci(),
            played_san=board.san(played),
            best_uci=best.uci(),
            best_san=board.san(best),
            best_score=best_score,
            played_score=played_score,
            loss_percent=loss,
            accuracy=move_accuracy(loss),
            classification=classify_move(
                loss,
                played_is_best=played == best,
                best=best_score,
                played=played_score,
                mover=board.turn,
            ),
            phase=game_phase(board),
            best_pv=tuple(move.uci() for move in best_line.moves),
            played_pv=tuple(move.uci() for move in played_line.moves),
            depth=min(best_line.depth, played_line.depth),
            evidence=evidence,
            tags=tuple(dict.fromkeys(fact.tag for fact in evidence)),
            deepened=deep,
        )
