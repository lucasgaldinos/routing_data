"""Configuration management for TSPLIB95 ETL Converter."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ConverterConfig:
  """Configuration for TSPLIB95 ETL Converter."""

  # Input settings
  input_path: str = "./datasets_raw/problems"
  file_patterns: list[str] = field(default_factory=lambda: ["*.tsp", "*.vrp", "*.atsp", "*.hcp", "*.sop", "*.tour"])

  # Output settings
  json_output_path: str = "./datasets/json"
  database_path: str = "./db/routing.duckdb"

  # Processing settings
  batch_size: int = 100
  max_workers: int = 4
  memory_limit_mb: int = 2048

  # Logging
  log_level: str = "INFO"
  log_file: str = "./logs/converter.log"

  def to_dict(self) -> dict[str, Any]:
    """Convert config to dictionary."""
    return asdict(self)


def load_config(config_path: str = "config.yaml") -> ConverterConfig:
  """
  Load configuration from YAML file.

  Args:
      config_path: Path to YAML configuration file

  Returns:
      ConverterConfig instance
  """
  config_file = Path(config_path)

  if config_file.exists():
    with open(config_file) as f:
      config_dict = yaml.safe_load(f) or {}
    return ConverterConfig(**config_dict)

  return ConverterConfig()


def save_config(config: ConverterConfig, config_path: str = "config.yaml") -> None:
  """
  Save configuration to YAML file.

  Args:
      config: ConverterConfig instance
      config_path: Path to save YAML file
  """
  config_file = Path(config_path)
  config_file.parent.mkdir(parents=True, exist_ok=True)

  with open(config_file, "w") as f:
    yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)
