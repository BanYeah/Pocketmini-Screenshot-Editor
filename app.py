import streamlit as st

import base64
import json
import xml.etree.ElementTree as ET
import cairosvg

from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, UnidentifiedImageError

BADGE_FILES = {
    "VIP": "vip.svg",
    "럭백": "lucky.svg",
    "현질": "cash.svg",
    "이벵": "event.svg",
}


# --- 설정 기본값 --- #
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


# --- 스티커 선택 --- #
def save_sticker_selection(file_id, row, col, sticker_key):
    st.session_state["sticker_selections"][file_id][row, col] = (
        st.session_state[sticker_key]
    )


# --- 이미지 미리보기 --- #
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


def crop_preview_image(source, top, bottom):
    width, height = source.size

    start = max(top, 0)
    end = min(bottom + 1, height)
    return source.crop((0, start, width, end))


def add_stickers_preview_image(preview, settings, selections):
    width, height = preview.size

    image_bytes = BytesIO()
    preview.save(image_bytes, format="PNG")

    namespace = "http://www.w3.org/2000/svg"
    ET.register_namespace("", namespace)

    svg = ET.Element(f"{{{namespace}}}svg", {
        "width": str(width), "height": str(height),
        "viewBox": f"0 0 {width} {height}", "overflow": "hidden",
    })

    ET.SubElement(svg, f"{{{namespace}}}image", {
        "width": str(width), "height": str(height),
        "href": f"data:image/png;base64,{base64.b64encode(image_bytes.getvalue()).decode("ascii")}",
    })

    for (row, col), selection in selections.items():
        if selection == "없음":
            continue
        badge_path = Path(__file__).parent / "badges" / BADGE_FILES[selection]
        badge = ET.parse(badge_path).getroot()
        badge.set("x", str(settings[f"col{col + 1}"]))
        badge.set("y", str(settings[f"row{row + 1}"] - settings["top"]))
        svg.append(badge)

    return ET.tostring(svg, encoding="unicode")


# --- PNG 복사 --- #
st.session_state.setdefault("copied_images", set())


def mark_image_copied(file_id):
    st.session_state["copied_images"].add(file_id)


@st.cache_resource
def copy_png_image():
    return st.components.v2.component(
        "copy_png_image",
        js="""
        export default function({ data, setTriggerValue }) {
            const selector = `.st-key-${CSS.escape(data.button_key)} button`;

            const bytes = Uint8Array.from(atob(data.png), c => c.charCodeAt(0));
            const png = new Blob([bytes], {type: "image/png"});

            let button;
            const copy = async event => {
                event.preventDefault();
                event.stopImmediatePropagation();
                if (!window.isSecureContext || !navigator.clipboard?.write || !window.ClipboardItem) {
                    window.alert("이미지 복사를 지원하는 브라우저에서 HTTPS 또는 localhost로 열어주세요.");
                    return;
                }

                button.disabled = true;
                try {
                    await navigator.clipboard.write([
                        new ClipboardItem({"image/png": png})
                    ]);
                    setTriggerValue("copied", true);
                } catch (error) {
                    window.alert("복사 실패: 클립보드 권한을 확인하세요.");
                } finally {
                    button.disabled = false;
                }
            };
            const bind = () => {
                const next = document.querySelector(selector);
                if (next === button) return;
                if (button) button.removeEventListener("click", copy, true);
                button = next;
                if (button) button.addEventListener("click", copy, true);
            };
            bind();

            const observer = new MutationObserver(bind);
            observer.observe(document.body, {childList: true, subtree: true});
            return () => {
                observer.disconnect();
                if (button) button.removeEventListener("click", copy, true);
            };
        }
        """,
        isolate_styles=False,
    )


# --- 로고 --- #
st.logo("logo.svg", size="large", link=None, icon_image=None)


# --- 사이드바 --- #
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


# --- 스티커 선택 변수 설정 --- #
sticker_selections = st.session_state.setdefault("sticker_selections", {})
for uploaded_file in uploaded_files or []:
    sticker_selections.setdefault(
        uploaded_file.file_id,
        {(row, col): "없음" for row in range(2) for col in range(5)},
    )

crop_tab, sticker_tab, result_tab = st.tabs(["이미지 자르기", "스티커", "결과"])

# --- 이미지 자르기 탭 --- #
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
            else:
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

# --- 스티커 탭 --- #
with sticker_tab:
    if uploaded_files:
        sorted_files = sorted(uploaded_files, key=lambda file: file.name)
        page_count = len(sorted_files)
        st.session_state["sticker_page"] = min(max(st.session_state.get("sticker_page", 1), 1), page_count)

        image_container = st.container()
        select_container = st.container()
        with st.container(horizontal=True, horizontal_alignment="center"):
            page = st.pagination(num_pages=page_count, key="sticker_page")

        uploaded_file = sorted_files[page - 1]
        selections = sticker_selections[uploaded_file.file_id]
        with select_container:
            for row in range(2):
                for col, column in enumerate(st.columns(5)):
                    with column:
                        sticker_key = f"sticker_{uploaded_file.file_id}_{row}_{col}"
                        if sticker_key not in st.session_state:
                            st.session_state[sticker_key] = selections[row, col]
                        st.selectbox(
                            f"{row + 1}행 {col + 1}열의 스티커를 선택하세요.",
                            options=["없음", "VIP", "럭백", "현질", "이벵"],
                            key=sticker_key,
                            on_change=save_sticker_selection,
                            args=(uploaded_file.file_id, row, col, sticker_key),
                            label_visibility="collapsed",
                        )
        with image_container:
            if settings["top"] > settings["bottom"]:
                st.warning("top은 bottom 이하로 설정하세요.")
            else:
                try:
                    with Image.open(BytesIO(uploaded_file.getvalue())) as source:
                        preview = crop_preview_image(
                            source, settings["top"], settings["bottom"]
                        )
                    preview = add_stickers_preview_image(preview, settings, selections)
                    st.image(preview)
                except (UnidentifiedImageError, OSError):
                    st.error("이미지 파일을 읽을 수 없습니다.")
    else:
        st.info("사이드바에서 이미지를 업로드하세요.")

# --- 결과 탭 --- #
with result_tab:
    if uploaded_files:
        if settings["top"] > settings["bottom"]:
            st.warning("top은 bottom 이하로 설정하세요.")
        else:
            sorted_files = sorted(uploaded_files, key=lambda file: file.name)
            for uploaded_file in sorted_files:
                try:
                    with Image.open(BytesIO(uploaded_file.getvalue())) as source:
                        preview = crop_preview_image(
                            source, settings["top"], settings["bottom"]
                        )
                    preview = add_stickers_preview_image(preview, settings, sticker_selections[uploaded_file.file_id])
                    png = cairosvg.svg2png(bytestring=preview.encode("utf-8"))

                    image_col, button_col = st.columns([9, 1], vertical_alignment="center")
                    with image_col:
                        st.image(png)
                    with button_col:
                        button_key = f"copy_image_{uploaded_file.file_id}"
                        copied = copy_png_image()(
                            data={
                                "button_key": button_key,
                                "name": uploaded_file.name,
                                "png": base64.b64encode(png).decode("ascii"),
                            },
                            key=f"clipboard_{uploaded_file.file_id}",
                            on_copied_change=lambda: None,
                        )
                        if copied.copied:
                            mark_image_copied(uploaded_file.file_id)
                        
                        st.button(
                            "복사",
                            key=button_key,
                            type="secondary" if uploaded_file.file_id in st.session_state["copied_images"] else "primary",
                        )
                except (UnidentifiedImageError, OSError):
                    st.error("이미지 파일을 읽을 수 없습니다.")
    else:
        st.info("사이드바에서 이미지를 업로드하세요.")
