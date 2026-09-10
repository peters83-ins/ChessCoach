"""Pinned official engine artifacts used by packaged Windows builds."""

from chesscoach.engine.download import EngineArtifact

STOCKFISH_WINDOWS_X64 = EngineArtifact(
    url=(
        "https://github.com/official-stockfish/Stockfish/releases/download/"
        "sf_19/stockfish-windows-x86-64-universal.zip"
    ),
    filename="stockfish-windows-x86-64-universal.zip",
    sha256="3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7",
    version="19",
    license_url="https://github.com/official-stockfish/Stockfish/blob/master/COPYING",
)
