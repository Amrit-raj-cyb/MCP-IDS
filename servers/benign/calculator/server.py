"""Benign Calculator MCP server, and the factory shared with its poisoned twin.

Simple explanation
------------------
A small calculator: add numbers, convert temperatures, compute percentages.
It has two jobs in the lab:

1. Benign traffic (calculator tasks, or just "mounted but unused").
2. **The clean twin of the poisoned-tool attack** (Phase 6). The attack server
   is built with :func:`build_calculator` too, so both servers have exactly
   the same tools, parameters, behaviour and on-the-wire name. *Only the
   description text differs.* Any difference the IDS finds between benign and
   attack sessions is then caused by the attack metadata, not by "a different
   server was present".

Note: no ``from __future__ import annotations`` here. Parameter descriptions
are built at run time inside :func:`build_calculator`, and the SDK must see
real ``Annotated`` objects, not strings.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Annotated

from common.logsetup import configure_server_logging
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

SERVER_NAME = "lab-calculator"  # identical for both twins (sent in initialize)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalculatorText:
    """All human/LLM-readable metadata of the calculator's tools."""
    add_numbers: str = "Add two numbers and return the sum."
    convert_temperature: str = "Convert a temperature between Celsius (C), Fahrenheit (F) and Kelvin (K)."
    percentage: str = "Compute what percentage `part` is of `whole`."
    params: dict[str, str] = field(default_factory=lambda: {
        "a": "First number.",
        "b": "Second number.",
        "value": "The temperature to convert.",
        "from_unit": "Unit of the input: C, F or K.",
        "to_unit": "Unit to convert to: C, F or K.",
        "part": "The part.",
        "whole": "The whole (must not be zero).",
    })


CLEAN_TEXT = CalculatorText()


def _to_kelvin(v: float, unit: str) -> float:
    return {"C": v + 273.15, "F": (v - 32) * 5 / 9 + 273.15, "K": v}[unit]


def _from_kelvin(k: float, unit: str) -> float:
    return {"C": k - 273.15, "F": (k - 273.15) * 9 / 5 + 32, "K": k}[unit]


def build_calculator(text: CalculatorText = CLEAN_TEXT) -> MCPServer:
    """Create a calculator server whose tool metadata comes from ``text``."""
    p = text.params
    server = MCPServer(name=SERVER_NAME, version="0.1.0",
                       instructions="Simple arithmetic and unit conversion tools.")

    def add_numbers(a: Annotated[float, Field(description=p["a"])],
                    b: Annotated[float, Field(description=p["b"])]) -> str:
        log.info("add_numbers %s + %s", a, b)
        return f"{a + b:g}"

    def convert_temperature(value: Annotated[float, Field(description=p["value"])],
                            from_unit: Annotated[str, Field(description=p["from_unit"])],
                            to_unit: Annotated[str, Field(description=p["to_unit"])]) -> str:
        units = {"C", "F", "K"}
        f, t = from_unit.upper(), to_unit.upper()
        if f not in units or t not in units:
            raise ToolError(f"Unknown unit; use one of {sorted(units)}")
        return f"{_from_kelvin(_to_kelvin(value, f), t):.2f} {t}"

    def percentage(part: Annotated[float, Field(description=p["part"])],
                   whole: Annotated[float, Field(description=p["whole"])]) -> str:
        if whole == 0:
            raise ToolError("whole must not be zero")
        return f"{part / whole * 100:.2f}%"

    server.add_tool(add_numbers, description=text.add_numbers)
    server.add_tool(convert_temperature, description=text.convert_temperature)
    server.add_tool(percentage, description=text.percentage)
    return server


def main() -> None:
    configure_server_logging("calculator")
    log.info("starting (clean); session=%s", os.getenv("MCP_SESSION_ID", "-"))
    build_calculator(CLEAN_TEXT).run("stdio")


if __name__ == "__main__":
    main()
