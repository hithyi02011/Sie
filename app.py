import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Pedigree Drawer (Table Input)", layout="wide")

# =============================
# 默认示例数据（表格）
# 你后续可以在网页里直接改，不用改代码
# =============================
DEFAULT_ROWS = [
    # 祖辈
    {"id":"P4","name":"祖父(父系)","sex":"M","affected":True,  "deceased":True,  "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P5","name":"祖母(父系)","sex":"F","affected":False, "deceased":False, "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P6","name":"外祖父","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P7","name":"外祖母","sex":"F","affected":True,  "deceased":True,  "father_id":"","mother_id":"","proband":False,"birth_order":None},

    # 父母
    {"id":"P2","name":"父亲","sex":"M","affected":False, "deceased":False, "father_id":"P4","mother_id":"P5","proband":False,"birth_order":None},
    {"id":"P3","name":"母亲","sex":"F","affected":False, "deceased":False, "father_id":"P6","mother_id":"P7","proband":False,"birth_order":None},

    # 同胞（按出生顺序显示）
    {"id":"P8","name":"姐姐","sex":"F","affected":False, "deceased":False, "father_id":"P2","mother_id":"P3","proband":False,"birth_order":1},
    {"id":"P1","name":"患者","sex":"F","affected":True,  "deceased":False, "father_id":"P2","mother_id":"P3","proband":True, "birth_order":2},
    {"id":"P9","name":"弟弟","sex":"M","affected":True,  "deceased":True,  "father_id":"P2","mother_id":"P3","proband":False,"birth_order":3},
]

# =============================
# DataFrame -> people(list)
# =============================
def to_bool(v):
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    s = str(v).strip().lower()
    return s in ["true", "1", "yes", "y", "是"]

def to_int_or_none(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        # data_editor 数值列有时会变 float
        return int(float(s))
    except Exception:
        return None

def df_to_people(df: pd.DataFrame):
    rows = []
    for _, r in df.iterrows():
        pid = str(r.get("id", "")).strip()
        if not pid:
            continue  # 跳过空行

        name = str(r.get("name", "")).strip() or pid
        sex = str(r.get("sex", "U")).strip().upper() or "U"

        father_id = str(r.get("father_id", "")).strip()
        mother_id = str(r.get("mother_id", "")).strip()
        father_id = father_id if father_id else None
        mother_id = mother_id if mother_id else None

        rows.append({
            "id": pid,
            "name": name,
            "sex": sex,
            "affected": to_bool(r.get("affected", False)),
            "deceased": to_bool(r.get("deceased", False)),
            "father_id": father_id,
            "mother_id": mother_id,
            "proband": to_bool(r.get("proband", False)),
            "birth_order": to_int_or_none(r.get("birth_order", None)),
        })
    return rows

# =============================
# 校验
# =============================
def validate_people(people):
    if not isinstance(people, list):
        raise ValueError("输入数据必须是列表。")

    ids = [p.get("id") for p in people]
    if any(i is None or str(i).strip() == "" for i in ids):
        raise ValueError("每个人都必须有 id。")
    if len(ids) != len(set(ids)):
        raise ValueError("存在重复 id，请检查（id 不能重复）。")

    id_set = set(ids)

    for p in people:
        sex = p.get("sex", "U")
        if sex not in ["M", "F", "U"]:
            raise ValueError(f"{p['id']} 的 sex 必须是 M/F/U。")

        for k in ["father_id", "mother_id"]:
            v = p.get(k)
            if v and v not in id_set:
                raise ValueError(f"{p['id']} 的 {k}={v} 不存在（请先添加该人物）。")

    # 先证者只能有一个（可选）
    probands = [p["id"] for p in people if p.get("proband")]
    if len(probands) > 1:
        raise ValueError(f"只能有一个患者（proband=True），当前有多个：{probands}")

    # 同父同母的子女：若填写了 birth_order，则不能重复
    fam_orders = {}
    for p in people:
        fid = p.get("father_id")
        mid = p.get("mother_id")
        bo = p.get("birth_order")
        if fid and mid and bo is not None:
            key = (fid, mid)
            fam_orders.setdefault(key, set())
            if bo in fam_orders[key]:
                raise ValueError(f"同一父母({fid},{mid})下出现重复 birth_order={bo}")
            fam_orders[key].add(bo)

# =============================
# 代际计算
# =============================
def compute_generations(people):
    person_map = {p["id"]: p for p in people}
    gen = {}

    def get_gen(pid, visiting=None):
        if pid in gen:
            return gen[pid]
        if visiting is None:
            visiting = set()
        if pid in visiting:
            # 避免异常循环数据卡死
            return 0
        visiting.add(pid)

        p = person_map[pid]
        fid = p.get("father_id")
        mid = p.get("mother_id")
        parent_gens = []
        if fid in person_map:
            parent_gens.append(get_gen(fid, visiting))
        if mid in person_map:
            parent_gens.append(get_gen(mid, visiting))

        g = 0 if not parent_gens else max(parent_gens) + 1
        gen[pid] = g
        visiting.remove(pid)
        return g

    for pid in person_map:
        get_gen(pid)

    return gen

# =============================
# 家庭单元：共同父母 -> 子女列表
# =============================
def build_families(people):
    person_map = {p["id"]: p for p in people}

    def child_sort_key(cid):
        p = person_map[cid]
        bo = p.get("birth_order")
        # 有 birth_order 的优先，按数字小->大（年长在左）
        # 没填的放后面，再按 id 稳定排序
        return (bo is None, bo if bo is not None else 999999, cid)

    families = {}
    for p in people:
        fid = p.get("father_id")
        mid = p.get("mother_id")
        if fid and mid:
            families.setdefault((fid, mid), []).append(p["id"])

    # 排序子女
    for k in families:
        families[k] = sorted(families[k], key=child_sort_key)

    return families

# =============================
# 布局（横平竖直）
# - 每代一行
# - 父母并排
# - 子女按 birth_order 排在下一代
# =============================
def layout_people(people):
    gen = compute_generations(people)
    families = build_families(people)

    gen_to_ids = {}
    for p in people:
        gen_to_ids.setdefault(gen[p["id"]], []).append(p["id"])

    # 可调参数
    x_gap = 130
    y_gap = 185
    margin_x = 80
    margin_y = 90

    coords = {}
    max_gen = max(gen_to_ids.keys()) if gen_to_ids else 0

    for g in range(max_gen + 1):
        y = margin_y + g * y_gap
        x_cursor = margin_x

        fams_this_gen = []
        for (fid, mid), children in families.items():
            if gen.get(fid) == g and gen.get(mid) == g:
                fams_this_gen.append((fid, mid, children))
        # 稳定顺序
        fams_this_gen.sort(key=lambda x: (x[0], x[1]))

        placed_in_gen = set()

        for fid, mid, children in fams_this_gen:
            # 父母位置（并排）
            if fid not in coords:
                coords[fid] = (x_cursor, y)
            if mid not in coords:
                coords[mid] = (x_cursor + x_gap, y)
            placed_in_gen.update([fid, mid])

            # 子女在下一代，围绕父母中点横向展开（按 birth_order）
            child_y = margin_y + (g + 1) * y_gap
            center_x = (coords[fid][0] + coords[mid][0]) / 2
            n = len(children)
            if n > 0:
                start_x = center_x - ((n - 1) * x_gap) / 2
                for i, cid in enumerate(children):
                    if cid not in coords:
                        coords[cid] = (start_x + i * x_gap, child_y)

            block_w = max(2 * x_gap, (max(1, n) - 1) * x_gap + x_gap)
            x_cursor += block_w + 100

        # 这一代剩余未放置人物（无配偶记录或孤立个体）
        leftovers = [pid for pid in sorted(gen_to_ids.get(g, [])) if pid not in placed_in_gen and pid not in coords]
        for pid in leftovers:
            coords[pid] = (x_cursor, y)
            x_cursor += x_gap

    if coords:
        max_x = max(x for x, _ in coords.values())
        max_y = max(y for _, y in coords.values())
    else:
        max_x, max_y = 600, 300

    width = int(max_x + 180)
    height = int(max_y + 210)
    return coords, families, width, height

# =============================
# SVG 绘制
# =============================
def line(x1, y1, x2, y2, w=2.5):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" stroke-width="{w}" />'

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def pedigree_to_svg(people, title="Pedigree", show_labels=True):
    validate_people(people)
    coords, families, width, height = layout_people(people)

    # 图形参数
    r = 26
    base_stroke = 2.6
    proband_stroke = 3.8
    spouse_line_w = 2.4
    label_font = 14
    label_offset = 50

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:white">'
    )
    svg.append(
        f'<text x="{width/2}" y="38" text-anchor="middle" font-size="22" '
        f'font-family="Arial, Microsoft YaHei">{esc(title)}</text>'
    )

    # 1) 连线（全部横平竖直）
    for (fid, mid), children in families.items():
        if fid not in coords or mid not in coords:
            continue
        fx, fy = coords[fid]
        mx, my = coords[mid]

        left_x, right_x = sorted([fx, mx])

        # 夫妻线
        svg.append(line(left_x, fy, right_x, fy, spouse_line_w))

        if children:
            center_x = (fx + mx) / 2
            y_sib = fy + 44  # 子代横线高度（父母线下方）

            valid_children = [cid for cid in children if cid in coords]
            if not valid_children:
                continue

            child_points = [(coords[cid][0], coords[cid][1]) for cid in valid_children]

            # 夫妻中点 -> 子代横线 竖线
            svg.append(line(center_x, fy, center_x, y_sib, spouse_line_w))

            xs = sorted([x for x, _ in child_points])

            # 子代横线（单个子女时可不画长横线）
            if len(xs) > 1:
                svg.append(line(xs[0], y_sib, xs[-1], y_sib, spouse_line_w))

            # 各子女竖线（接到图形上沿）
            for cx, cy in child_points:
                if len(xs) == 1 and cx != center_x:
                    svg.append(line(center_x, y_sib, cx, y_sib, spouse_line_w))
                svg.append(line(cx, y_sib, cx, cy - r, spouse_line_w))

    # 2) 人物图形
    proband_ids = []
    for p in people:
        pid = p["id"]
        x, y = coords[pid]
        sex = p.get("sex", "U")
        affected = bool(p.get("affected", False))
        deceased = bool(p.get("deceased", False))
        proband = bool(p.get("proband", False))
        name = p.get("name", pid)

        if proband:
            proband_ids.append(pid)

        fill = "black" if affected else "white"
        stroke_w = proband_stroke if proband else base_stroke

        # 主图形
        if sex == "M":
            # 方块
            svg.append(
                f'<rect x="{x-r}" y="{y-r}" width="{2*r}" height="{2*r}" '
                f'fill="{fill}" stroke="black" stroke-width="{stroke_w}" />'
            )
        elif sex == "F":
            # 圆
            svg.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" '
                f'stroke="black" stroke-width="{stroke_w}" />'
            )
        else:
            # 菱形
            pts = f"{x},{y-r} {x+r},{y} {x},{y+r} {x-r},{y}"
            svg.append(
                f'<polygon points="{pts}" fill="{fill}" stroke="black" stroke-width="{stroke_w}" />'
            )

        # 死亡斜杠（伸出图形外，强调是斜杠）
        if deceased:
            # 左下 -> 右上，故意伸出图形边界
            ex = r + 10
            ey = r + 10
            svg.append(
                line(x - ex, y + ey, x + ex, y - ey, 3.0)
            )

        # 标签
        if show_labels:
            svg.append(
                f'<text x="{x}" y="{y+label_offset}" text-anchor="middle" '
                f'font-size="{label_font}" font-family="Arial, Microsoft YaHei">{esc(name)}</text>'
            )

    # 3) 先证者箭头（离远一点，避免贴得太近）
    # 简化策略：从左上方向指向患者；如果空间不足再从右上
    for pid in proband_ids:
        x, y = coords[pid]

        # 默认左上箭头（离远一点）
        ax1, ay1 = x - 78, y - 62   # 箭尾（更远）
        ax2, ay2 = x - 18, y - 14   # 箭尖（靠近图形但不贴边）

        # 如果太靠左，改从右上
        if ax1 < 10:
            ax1, ay1 = x + 78, y - 62
            ax2, ay2 = x + 18, y - 14

        # 箭身
        svg.append(line(ax1, ay1, ax2, ay2, 2.4))
        # 箭头头（V形）
        if ax2 < x:  # 从左侧来
            svg.append(line(ax2, ay2, ax2 - 9, ay2 - 2, 2.4))
            svg.append(line(ax2, ay2, ax2 - 2, ay2 - 9, 2.4))
        else:       # 从右侧来
            svg.append(line(ax2, ay2, ax2 + 9, ay2 - 2, 2.4))
            svg.append(line(ax2, ay2, ax2 + 2, ay2 - 9, 2.4))

    svg.append("</svg>")
    return "".join(svg)

# =============================
# UI
# =============================
st.title("家系图绘制器（网页填表版｜纯事实）")
st.caption("网页里直接填家庭成员信息；支持出生顺序、死亡斜杠、先证者箭头。")

# session_state 初始化
if "pedigree_df" not in st.session_state:
    st.session_state.pedigree_df = pd.DataFrame(DEFAULT_ROWS)

top1, top2, top3 = st.columns([1, 1, 1])
with top1:
    if st.button("加载示例数据"):
        st.session_state.pedigree_df = pd.DataFrame(DEFAULT_ROWS)
with top2:
    if st.button("清空表格"):
        st.session_state.pedigree_df = pd.DataFrame(
            columns=["id","name","sex","affected","deceased","father_id","mother_id","proband","birth_order"]
        )
with top3:
    show_labels = st.checkbox("显示姓名标签", value=True)

st.markdown("### 1) 在表格里填写家族成员信息（每行一个人）")

edited_df = st.data_editor(
    st.session_state.pedigree_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.TextColumn("id", help="唯一编号，不能重复，例如 P1/P2"),
        "name": st.column_config.TextColumn("姓名/称谓", help="如 患者、父亲、母亲、大哥、二姐"),
        "sex": st.column_config.SelectboxColumn("性别", options=["M", "F", "U"], help="M男 F女 U不明"),
        "affected": st.column_config.CheckboxColumn("患病", help="勾选=实心；不勾=空心"),
        "deceased": st.column_config.CheckboxColumn("死亡", help="勾选=图形加斜杠"),
        "father_id": st.column_config.TextColumn("父亲id", help="填写父亲的 id（不是名字）"),
        "mother_id": st.column_config.TextColumn("母亲id", help="填写母亲的 id（不是名字）"),
        "proband": st.column_config.CheckboxColumn("患者(先证者)", help="只能有一个；会加粗边框+箭头"),
        "birth_order": st.column_config.NumberColumn(
            "出生顺序",
            help="同一父母下子女排序：1=最大，2=次大，3=更小……（左到右）",
            step=1,
            min_value=1
        ),
    },
    key="data_editor_pedigree"
)

graph_title = st.text_input("2) 图标题", value="Pedigree")

if st.button("3) 生成家系图", type="primary"):
    try:
        st.session_state.pedigree_df = edited_df.copy()
        people = df_to_people(edited_df)

        if len(people) == 0:
            st.warning("表格是空的，请先添加至少一位成员。")
        else:
            svg_html = pedigree_to_svg(people, title=graph_title, show_labels=show_labels)

            st.markdown("### 生成结果")
            components.html(svg_html, height=780, scrolling=True)

            with st.expander("查看当前结构化数据（调试用）", expanded=False):
                st.json(people)

            st.success("已根据网页表格输入生成家系图。")

    except Exception as e:
        st.error(f"生成失败：{e}")

with st.expander("填写说明（第一次建议看）", expanded=False):
    st.markdown("""
**每一行代表一个人。**

- `id`：唯一编号（例如 `P1`, `P2`）
- `姓名/称谓`：图上显示文字（例如“患者”“父亲”“大哥”“二姐”）
- `性别`：`M` 男，`F` 女，`U` 不明
- `患病`：勾选=实心；不勾选=空心
- `死亡`：勾选=图形上画斜杠（斜杠会伸出图形外）
- `父亲id` / `母亲id`：填写对应人物的 `id`（不是名字）
- `患者(先证者)`：只能有一个，会加粗边框并画箭头
- `出生顺序`：同一父母下子女排序（`1` 最大、`2` 次大、`3` 更小…），从左到右显示

### 常见场景
如果患者有 **大哥、二姐、患者、妹妹**，并且父母都是 `P2/P3`，可以这样填：
- 大哥：`birth_order = 1`
- 二姐：`birth_order = 2`
- 患者：`birth_order = 3`
- 妹妹：`birth_order = 4`

没填的人不会出现在图上；只有你在表格里填了的人才会画出来。
""")
