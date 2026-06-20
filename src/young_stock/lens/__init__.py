"""Investor lens plugin layer."""

from .contracts import LensResult, build_lens_result, parse_lens_result
from .engine import build_lens_prompt, run_lens_engine
from .registry import LENSES, LensDefinition, get_lens, lens_ids

__all__ = [
    "LENSES",
    "LensDefinition",
    "LensResult",
    "build_lens_prompt",
    "build_lens_result",
    "get_lens",
    "lens_ids",
    "parse_lens_result",
    "run_lens_engine",
]
