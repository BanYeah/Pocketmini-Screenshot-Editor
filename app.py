import json
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, UnidentifiedImageError


with Path("setting.jsonl").open(encoding="utf-8") as file:
    presets = {
        setting["tag"]: setting
        for line in file
        if line.strip()
        for setting in [json.loads(line)]
    }


def apply_preset():
    preset = presets[st.session_state["selected_preset"]]
    for name, value in preset.items():
        if name != "tag":
            st.session_state[f"setting_{name}"] = value


def setting_input(name, preset):
    key = f"setting_{name}"
    if key not in st.session_state:
        st.session_state[key] = preset[name]
    return st.number_input(name, step=1, key=key)


def preview_image(source, top, bottom, guidelines=None):
    preview = source.convert("RGBA")
    width, height = preview.size

    overlay = Image.new("RGBA", preview.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    top_end = min(max(top, 0), height)
    bottom_start = min(max(bottom + 1, 0), height)
    if top_end > 0:
        draw.rectangle((0, 0, width - 1, top_end - 1), fill=(0, 0, 0, 160))
    if bottom_start < height:
        draw.rectangle((0, bottom_start, width - 1, height - 1), fill=(0, 0, 0, 160))
    
    preview = Image.alpha_composite(preview, overlay)
    if guidelines is not None:
        guide_draw = ImageDraw.Draw(preview)
        for name in ("row1", "row2"):
            y = guidelines[name]
            if 0 <= y < height:
                guide_draw.line((0, y, width - 1, y), fill="#50ADF0", width=2)
        for name in ("col1", "col2", "col3", "col4", "col5"):
            x = guidelines[name]
            if 0 <= x < width:
                guide_draw.line((x, 0, x, height - 1), fill="#ED59FA", width=2)
    return preview


st.logo("logo.svg", size="large", link=None, icon_image=None)

with st.sidebar:
    uploaded_files = st.file_uploader(
        "이미지를 업로드하세요.",
        type=["jpg", "jpeg", "png", "gif", "bmp", "webp"],
        accept_multiple_files=True,
    )
    st.divider()

    st.selectbox(
        "설정 기본값 선택",
        options=list(presets),
        key="selected_preset",
        on_change=apply_preset,
    )

    preset = presets[st.session_state["selected_preset"]]
    settings = {"tag": preset["tag"]}
    
    for names in [("top", "bottom"), ("row1", "row2")]:
        for column, name in zip(st.columns(2), names):
            with column:
                settings[name] = setting_input(name, preset)

    with st.expander("col1 ~ col5", expanded=False):
        for name in ("col1", "col2", "col3", "col4", "col5"):
            settings[name] = setting_input(name, preset)
    st.divider()

crop_tab, sticker_tab, result_tab = st.tabs(["이미지 자르기", "스티커", "결과"])

with crop_tab:
    if uploaded_files:
        sorted_files = sorted(uploaded_files, key=lambda file: file.name)
        page_count = len(sorted_files)
        st.session_state["image_page"] = min(max(st.session_state.get("image_page", 1), 1), page_count)

        image_container = st.container()
        with st.container(horizontal=True, horizontal_alignment="center"):
            page = st.pagination(num_pages=page_count, key="image_page")

        uploaded_file = sorted_files[page - 1]
        with image_container:
            if settings["top"] > settings["bottom"]:
                st.warning("top은 bottom 이하로 설정하세요.")
            try:
                on = st.toggle("스티커 가이드라인 표시")
                with Image.open(BytesIO(uploaded_file.getvalue())) as source:
                    preview = preview_image(
                        source, settings["top"], settings["bottom"],
                        guidelines=settings if on else None,
                    )
                st.image(preview)
            except (UnidentifiedImageError, OSError):
                st.error("이미지 파일을 읽을 수 없습니다.")
    else:
        st.info("사이드바에서 이미지를 업로드하세요.")
