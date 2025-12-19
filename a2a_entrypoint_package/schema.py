"""
Pydantic models for the *white agent* output in your benchmark context.

Top-level keys are aligned with your validated example JSON:
- paper
- equations
- extraction_metadata

Must-have fields for each equation object:
- latex
- model_performance
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

class Paper(BaseModel):
    model_config = ConfigDict(extra="allow")
    doi: Optional[str] = None
    title: Optional[str] = None
    year: Optional[Union[int, str]] = None

class Equation(BaseModel):
    """
    Minimal required fields + allow extras.
    Your extractor can include additional fields as needed.
    """
    model_config = ConfigDict(extra="allow")
    latex: Optional[str] = Field(default=None, description="LaTeX math for the equation; null if not explicitly given.")
    model_performance: Optional[Any] = Field(default=None, description="Reported metrics (e.g., R2, RMSE); null if not reported.")

class ExtractionMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    task_id: Optional[str] = None
    input_doi: Optional[str] = None
    schema_name: Optional[str] = None
    schema_version: Optional[str] = None

class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    paper: Paper
    equations: List[Equation]
    extraction_metadata: ExtractionMetadata
