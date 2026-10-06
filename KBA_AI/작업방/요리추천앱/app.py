import os
import re
from datetime import date
from pathlib import Path

import gradio as gr
import pandas as pd

from core.ai_recipe import (
    AiGenerationError,
    AiUnavailableError,
    ai_available,
    generate_recipes,
)
from core.catalog import CATALOG, CATEGORIES, UNITS, default_for
from core.expiry import (
    STATUS_EXPIRED,
    STATUS_EXPIRING,
    expiry_status,
    parse_expiry,
)
from core.formatting import (
    INVENTORY_HEADERS,
    RECIPE_HEADERS,
    RECOMMEND_HEADERS,
    SHORTAGE_HEADERS,
    format_quantity,
    inventory_rows,
    recipe_detail,
    recipe_rows,
    recommendation_rows,
    shortage_rows,
)
from core.inventory_store import InventoryStore
from core.normalize import normalize
from core.recipe_store import RecipeStore
from core.recommender import ALMOST, READY, missing_summary, recommend, usable_items

BASE_DIR = Path(__file__).parent
store = InventoryStore(os.environ.get("PANTRY_DB_PATH") or BASE_DIR / "data" / "pantry.db")
recipes = RecipeStore(BASE_DIR / "data" / "recipes.json")

EMPTY_DETAIL = "요리를 선택하면 재료 분량과 조리 순서가 여기에 표시됩니다."


def today() -> date:
    return date.today()


def owned_names() -> set[str]:
    return {normalize(i.name) for i in usable_items(store.list_items(), today())}


def style_inventory(rows: list[list]):
    frame = pd.DataFrame(rows, columns=INVENTORY_HEADERS)

    def color(value: str) -> str:
        if str(value).startswith(STATUS_EXPIRED):
            return "background-color: #f8d7da; color: #58151c"
        if str(value).startswith(STATUS_EXPIRING):
            return "background-color: #fff3cd; color: #664d03"
        return ""

    return frame.style.map(color, subset=["상태"])


def inventory_summary() -> str:
    items = store.list_items()
    if not items:
        return "등록된 재료가 없습니다. 아래에서 재료를 추가하세요."
    t = today()
    statuses = [expiry_status(i.expiry, t) for i in items]
    text = f"재료 {len(items)}개"
    expiring = [i.name for i, s in zip(items, statuses) if s == STATUS_EXPIRING]
    expired = [i.name for i, s in zip(items, statuses) if s == STATUS_EXPIRED]
    if expiring:
        text += f" | 임박 {len(expiring)}개 ({', '.join(expiring)})"
    if expired:
        text += f" | 만료 {len(expired)}개 ({', '.join(expired)})"
    return text


def render_inventory(category: str):
    t = today()
    items = store.list_items(category)
    recs = recommend(store.list_items(), recipes.all(), t)
    return (
        style_inventory(inventory_rows(items, t)),
        pd.DataFrame(shortage_rows(missing_summary(recs)), columns=SHORTAGE_HEADERS),
        inventory_summary(),
    )


def build_inventory_page(demo: gr.Blocks):
    gr.Markdown("## 재료 목록")
    summary = gr.Markdown()

    with gr.Row(equal_height=False):
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab("직접 입력"):
                    name = gr.Textbox(label="재료명", placeholder="예: 양파")
                    with gr.Row():
                        qty = gr.Number(label="수량", value=1, minimum=0)
                        unit = gr.Dropdown(UNITS, value="개", label="단위", allow_custom_value=True)
                    expiry = gr.Textbox(label="유통기한 (선택)", placeholder="YYYY-MM-DD")
                    category = gr.Dropdown(CATEGORIES, value="기타", label="분류")
                    add_btn = gr.Button("추가", variant="primary")
                with gr.Tab("빠른 입력"):
                    quick = gr.Textbox(
                        label="재료를 쉼표로 구분해 입력",
                        placeholder="양파, 계란, 두부",
                        lines=3,
                    )
                    quick_btn = gr.Button("추가", variant="primary")
                with gr.Tab("자주 쓰는 재료"):
                    groups = [
                        gr.CheckboxGroup(choices=[n for n, _ in rows], label=cat)
                        for cat, rows in CATALOG.items()
                    ]
                    pick_btn = gr.Button("선택한 재료 추가", variant="primary")

            gr.Markdown("### 선택한 재료 수정 / 삭제")
            selected_id = gr.State(None)
            selected_label = gr.Markdown("표에서 재료를 선택하세요.")
            with gr.Row():
                edit_qty = gr.Number(label="수량", minimum=0)
                edit_expiry = gr.Textbox(label="유통기한", placeholder="YYYY-MM-DD")
            with gr.Row():
                update_btn = gr.Button("수정")
                delete_btn = gr.Button("삭제", variant="stop")

        with gr.Column(scale=3):
            category_filter = gr.Dropdown(["전체", *CATEGORIES], value="전체", label="분류 필터")
            inventory_df = gr.Dataframe(
                headers=INVENTORY_HEADERS, interactive=False, wrap=True, max_height=380
            )
            gr.Markdown("### 부족한 재료\n필수 재료가 1~2개 부족한 요리를 만들려면 필요한 재료입니다.")
            shortage_df = gr.Dataframe(headers=SHORTAGE_HEADERS, interactive=False, wrap=True, max_height=260)

    views = [inventory_df, shortage_df, summary]

    def add_single(n, q, u, e, c, flt):
        try:
            item, merged = store.add(n, q, u, parse_expiry(e), c)
        except ValueError as exc:
            gr.Warning(str(exc))
            return (*render_inventory(flt), gr.skip())
        gr.Info(f"'{item.name}' 수량을 합쳤습니다." if merged else f"'{item.name}'을(를) 추가했습니다.")
        return (*render_inventory(flt), "")

    def add_names(names: list[str], flt):
        added, merged = 0, 0
        for n in names:
            cat, u = default_for(n)
            _, was_merged = store.add(n, 1, u, None, cat)
            merged += was_merged
            added += not was_merged
        return added, merged

    def add_quick(text, flt):
        names = [n.strip() for n in re.split(r"[,，\n]", text or "") if n.strip()]
        if not names:
            gr.Warning("추가할 재료를 입력하세요.")
            return (*render_inventory(flt), gr.skip())
        added, merged = add_names(names, flt)
        gr.Info(f"{added}개 추가, {merged}개 수량 합침")
        return (*render_inventory(flt), "")

    def add_picked(flt, *selected):
        names = [n for group in selected for n in group]
        if not names:
            gr.Warning("추가할 재료를 선택하세요.")
            return (*render_inventory(flt), *[gr.skip() for _ in groups])
        added, merged = add_names(names, flt)
        gr.Info(f"{added}개 추가, {merged}개 수량 합침")
        return (*render_inventory(flt), *[[] for _ in groups])

    def on_select(evt: gr.SelectData):
        item = store.get(int(evt.row_value[0]))
        if item is None:
            return None, "존재하지 않는 재료입니다.", None, ""
        label = f"**{item.name}** ({item.category}, 단위: {item.unit})"
        return item.id, label, item.quantity, item.expiry.isoformat() if item.expiry else ""

    def update_selected(item_id, q, e, flt):
        if item_id is None:
            gr.Warning("수정할 재료를 먼저 선택하세요.")
            return render_inventory(flt)
        try:
            item = store.update(int(item_id), q, parse_expiry(e))
        except ValueError as exc:
            gr.Warning(str(exc))
            return render_inventory(flt)
        gr.Info(f"'{item.name}'을(를) 수정했습니다. (수량 {format_quantity(item.quantity)}{item.unit})")
        return render_inventory(flt)

    def delete_selected(item_id, flt):
        if item_id is None:
            gr.Warning("삭제할 재료를 먼저 선택하세요.")
            return (*render_inventory(flt), item_id, gr.skip(), gr.skip(), gr.skip())
        store.delete(int(item_id))
        gr.Info("재료를 삭제했습니다.")
        return (*render_inventory(flt), None, "표에서 재료를 선택하세요.", None, "")

    demo.load(render_inventory, inputs=category_filter, outputs=views)
    category_filter.change(render_inventory, inputs=category_filter, outputs=views)
    name.blur(lambda n: default_for(n) if n.strip() else (gr.skip(), gr.skip()), inputs=name, outputs=[category, unit])
    add_btn.click(add_single, inputs=[name, qty, unit, expiry, category, category_filter], outputs=[*views, name])
    name.submit(add_single, inputs=[name, qty, unit, expiry, category, category_filter], outputs=[*views, name])
    quick_btn.click(add_quick, inputs=[quick, category_filter], outputs=[*views, quick])
    pick_btn.click(add_picked, inputs=[category_filter, *groups], outputs=[*views, *groups])
    inventory_df.select(on_select, outputs=[selected_id, selected_label, edit_qty, edit_expiry])
    update_btn.click(update_selected, inputs=[selected_id, edit_qty, edit_expiry, category_filter], outputs=views)
    delete_btn.click(
        delete_selected,
        inputs=[selected_id, category_filter],
        outputs=[*views, selected_id, selected_label, edit_qty, edit_expiry],
    )


def recommendation_summary(recs, items) -> str:
    if not items:
        return "등록된 재료가 없습니다. '재료 목록' 페이지에서 먼저 재료를 추가하세요."
    ready = sum(r.verdict == READY for r in recs)
    almost = sum(r.verdict == ALMOST for r in recs)
    if not recs:
        return "지금 재료로 만들 수 있는 요리가 데이터셋에 없습니다."
    return f"바로 가능 {ready}개 | 조금 부족 {almost}개"


def run_ai(auto: bool = False):
    """현재 재료로 AI 레시피를 생성한다. (데이터프레임 행, 이름->레시피 맵, 안내 문구)를 돌려준다."""
    names = [i.name for i in usable_items(store.list_items(), today())]
    if not names:
        return [], {}, "재료를 먼저 등록하세요."
    try:
        generated = generate_recipes(names)
    except AiUnavailableError as exc:
        return [], {}, f"AI 추천을 사용할 수 없습니다. {exc}"
    except AiGenerationError as exc:
        return [], {}, str(exc)
    note = "데이터셋에 맞는 요리가 없어 AI가 생성한 레시피입니다. 저장되지 않습니다." if auto else "AI가 생성한 레시피입니다. 저장되지 않습니다."
    return recipe_rows(generated), {r.name: r for r in generated}, note


def build_recommend_page(demo: gr.Blocks):
    gr.Markdown("## 추천 레시피")
    summary = gr.Markdown()
    with gr.Row(equal_height=False):
        with gr.Column(scale=3):
            rec_df = gr.Dataframe(headers=RECOMMEND_HEADERS, interactive=False, wrap=True, max_height=420)
        with gr.Column(scale=2):
            detail = gr.Markdown(EMPTY_DETAIL)

    gr.Markdown("### AI 추천")
    ai_note = gr.Markdown()
    ai_btn = gr.Button("AI 레시피 생성")
    ai_df = gr.Dataframe(headers=RECIPE_HEADERS, interactive=False, wrap=True, max_height=240)
    ai_state = gr.State({})

    def load():
        items = store.list_items()
        recs = recommend(items, recipes.all(), today())
        rows = recommendation_rows(recs)
        ai_rows, ai_map, note = [], {}, ""
        if items and not recs:
            if ai_available():
                ai_rows, ai_map, note = run_ai(auto=True)
            else:
                note = "AI 추천을 사용하려면 OPENAI_API_KEY 환경변수를 설정하세요."
        elif not ai_available():
            note = "AI 추천을 사용하려면 OPENAI_API_KEY 환경변수를 설정하세요."
        return (
            pd.DataFrame(rows, columns=RECOMMEND_HEADERS),
            recommendation_summary(recs, items),
            EMPTY_DETAIL,
            pd.DataFrame(ai_rows, columns=RECIPE_HEADERS),
            ai_map,
            note,
        )

    def on_ai_click():
        ai_rows, ai_map, note = run_ai()
        return pd.DataFrame(ai_rows, columns=RECIPE_HEADERS), ai_map, note

    def on_rec_select(evt: gr.SelectData):
        recipe = recipes.get(evt.row_value[0])
        return recipe_detail(recipe, owned_names()) if recipe else EMPTY_DETAIL

    def on_ai_select(evt: gr.SelectData, ai_map):
        recipe = ai_map.get(evt.row_value[0])
        return recipe_detail(recipe, owned_names()) if recipe else EMPTY_DETAIL

    demo.load(load, outputs=[rec_df, summary, detail, ai_df, ai_state, ai_note])
    ai_btn.click(on_ai_click, outputs=[ai_df, ai_state, ai_note])
    rec_df.select(on_rec_select, outputs=detail)
    ai_df.select(on_ai_select, inputs=ai_state, outputs=detail)


def build_all_recipes_page(demo: gr.Blocks):
    gr.Markdown("## 전체 레시피")
    query = gr.Textbox(label="검색", placeholder="요리 이름 또는 재료 (예: 김치, 계란)")
    with gr.Row(equal_height=False):
        with gr.Column(scale=3):
            df = gr.Dataframe(headers=RECIPE_HEADERS, interactive=False, wrap=True, max_height=520)
        with gr.Column(scale=2):
            detail = gr.Markdown(EMPTY_DETAIL)

    def search(q):
        return pd.DataFrame(recipe_rows(recipes.search(q)), columns=RECIPE_HEADERS), EMPTY_DETAIL

    def on_select(evt: gr.SelectData):
        recipe = recipes.get(evt.row_value[0])
        return recipe_detail(recipe, owned_names()) if recipe else EMPTY_DETAIL

    demo.load(search, inputs=query, outputs=[df, detail])
    query.change(search, inputs=query, outputs=[df, detail])
    df.select(on_select, outputs=detail)


with gr.Blocks(title="냉장고 요리 추천") as demo:
    gr.Navbar(main_page_name="재료 목록")
    build_inventory_page(demo)

with demo.route("추천 레시피", "/recommend"):
    build_recommend_page(demo)

with demo.route("전체 레시피", "/recipes"):
    build_all_recipes_page(demo)


if __name__ == "__main__":
    demo.launch()
