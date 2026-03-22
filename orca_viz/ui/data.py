from __future__ import annotations

import copy
from io import StringIO
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd
import streamlit as st

from .. import load_gbw_file, parse_cube_file, parse_orca_file
from ..cube import CubeData
from ..gbw import GbwData
from ..i18n import tr
from ..pathway import (
    HARTREE_TO_KCAL_MOL,
    PathwayResult,
    build_path_display_dataframe,
)
from ..parser import OrcaParseResult


def normalize_gbw_sidecar_name(stem: str, upload_name: str) -> str | None:
    lowered = upload_name.lower()
    if lowered.endswith(".property.json"):
        return f"{stem}.property.json"
    if lowered.endswith(".densitiesinfo"):
        return f"{stem}.densitiesinfo"
    if lowered.endswith(".densities"):
        return f"{stem}.densities"
    if lowered.endswith(".property.txt"):
        return f"{stem}.property.txt"
    if lowered.endswith(".xyz"):
        return f"{stem}.xyz"
    if lowered.endswith(".out"):
        return f"{stem}.out"
    if lowered.endswith(".log"):
        return f"{stem}.log"
    return None


def load_single_input(
    uploaded_file: Any,
    local_path: str,
    gbw_sidecar_uploads: list[Any] | None = None,
) -> tuple[Any, str] | None:
    if uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix.lower()
        temp_dir = Path(tempfile.mkdtemp(prefix="orca_viz_input_"))
        temp_path = temp_dir / uploaded_file.name
        temp_path.write_bytes(uploaded_file.getbuffer())
        if suffix == ".gbw":
            for sidecar_upload in gbw_sidecar_uploads or []:
                target_name = normalize_gbw_sidecar_name(temp_path.stem, sidecar_upload.name)
                if target_name is None:
                    continue
                sidecar_path = temp_dir / target_name
                sidecar_path.write_bytes(sidecar_upload.getbuffer())
        return parse_path(temp_path, source_name=uploaded_file.name)

    if local_path.strip():
        path = Path(local_path.strip()).expanduser()
        if not path.exists():
            st.error(tr("文件不存在：{path}", path=path))
            return None
        return parse_path(path)

    return None


def load_batch_inputs(uploaded_files: list[Any], folder_path: str) -> list[Any]:
    items: list[Any] = []
    for uploaded_file in uploaded_files or []:
        loaded = load_single_input(uploaded_file, "")
        if loaded is not None:
            items.append(loaded[0])

    if folder_path.strip():
        folder = Path(folder_path.strip()).expanduser()
        if not folder.exists() or not folder.is_dir():
            st.error(tr("文件夹不存在：{folder}", folder=folder))
            return items
        patterns = ["*.out", "*.log", "*.txt", "*.xyz", "*.cube", "*.interp"]
        paths: list[Path] = []
        for pattern in patterns:
            paths.extend(folder.rglob(pattern))
        for path in sorted(set(paths)):
            try:
                parsed, _ = parse_path(path)
            except Exception as exc:
                st.warning(tr("跳过 {name}: {error}", name=path.name, error=exc))
                continue
            items.append(parsed)

    return items


def parse_path(path: Path, source_name: str | None = None) -> tuple[Any, str]:
    cached_item, cached_kind = _parse_path_cached(*_path_cache_key(path))
    parsed_item = copy.deepcopy(cached_item)
    if source_name and hasattr(parsed_item, "source_name"):
        parsed_item.source_name = source_name
    return parsed_item, cached_kind


@st.cache_data(show_spinner=False)
def _parse_path_cached(path_text: str, mtime_ns: int, size: int) -> tuple[Any, str]:
    return _parse_path_uncached(Path(path_text))


def _path_cache_key(path: Path) -> tuple[str, int, int]:
    resolved = path.expanduser().resolve()
    stat_result = resolved.stat()
    return str(resolved), int(stat_result.st_mtime_ns), int(stat_result.st_size)


def _parse_path_uncached(path: Path) -> tuple[Any, str]:
    suffix = path.suffix.lower()
    if suffix == ".cube":
        cube = parse_cube_file(path)
        return cube, "cube"
    if suffix == ".gbw":
        gbw = load_gbw_file(path)
        return gbw, "gbw"

    result = parse_orca_file(path)
    return result, "orca"


def download_dataframe(label: str, dataframe: pd.DataFrame, file_name: str) -> None:
    csv_buffer = StringIO()
    dataframe.to_csv(csv_buffer, index=False)
    st.download_button(label=label, data=csv_buffer.getvalue(), file_name=file_name)


def path_display_dataframe(
    dataframe: pd.DataFrame,
    x_col: str,
    y_col: str,
    *,
    kind: str = "trajectory",
    reference_mode: str = "minimum",
    reference_selector: str | int | float | None = None,
) -> pd.DataFrame:
    pathway = PathwayResult(kind=kind, points_df=dataframe)
    display_df = build_path_display_dataframe(
        pathway,
        reference_mode=reference_mode,  # type: ignore[arg-type]
        reference_selector=reference_selector,
        energy_col=y_col,
    )
    if x_col in display_df.columns:
        return display_df.sort_values(x_col, kind="mergesort").reset_index(drop=True)
    return display_df.reset_index(drop=True)


def localize_process_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    from .labels import process_category_label, process_reason_text, process_risk_label

    localized = dataframe.copy()
    if "category" in localized:
        localized["category"] = localized["category"].map(process_category_label)
    if "risk" in localized:
        localized["risk"] = localized["risk"].map(process_risk_label)
    if "resident" in localized:
        localized["resident"] = localized["resident"].map(lambda value: tr("是") if value else tr("否"))
    if "reasons" in localized:
        localized["reasons"] = localized["reasons"].map(process_reason_text)

    return localized.rename(
        columns={
            "pid": "PID",
            "ppid": "PPID",
            "process": tr("进程"),
            "category": tr("类别"),
            "risk": tr("风险等级"),
            "cpu_percent": tr("CPU 占用 (%)"),
            "memory_percent": tr("内存占用 (%)"),
            "elapsed": tr("驻留时长"),
            "resident": tr("后台驻留"),
            "reasons": tr("原因"),
            "command": tr("命令"),
        }
    )


def is_orca_result(item: Any) -> bool:
    return isinstance(item, OrcaParseResult)


def is_cube(item: Any) -> bool:
    return isinstance(item, CubeData)


def is_gbw(item: Any) -> bool:
    return isinstance(item, GbwData)
