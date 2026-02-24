import json
import streamlit as st
from graphviz import Digraph

st.set_page_config(page_title="Pedigree Drawer", layout="wide")

# -----------------------------
# 示例 JSON（你可以直接改）
# -----------------------------
DEFAULT_JSON = json.dumps(
    [
        {"id":"P1","name":"患者","sex":"F","affected":True,"father_id":"P2","mother_id":"P3","proband":True},
        {"id":"P2","name":"父亲","sex":"M","affected":False,"father_id":"P4","mother_id":"P5"},
        {"id":"P3","name":"母亲","sex":"F","affected":False,"father_id":"P6","mother_id":"P7"},
        {"id":"P4","name":"祖父(父系)","sex":"M","affected":True},
        {"id":"P5","name":"祖母(父系)","sex":"F","affected":False},
        {"id":"P6","name":"外祖父","sex":"M","affected":False},
        {"id":"P7","name":"外祖母","sex":"F","affected":True},
        {"id":"P8","name":"姐姐","sex":"F","affected":False,"father_id":"P2","mother_id":"P3"},
        {"id":"P9","name":"弟弟","sex":"M","affected":True,"father_id":"P2","mother_id":"P3"}
    ],
    ensure_ascii=False,
    indent=2
)

# -----------------------------
# 数据校验
# -----------------------------
def validate_people(people):
    if not isinstance(people, list):
        raise ValueError("JSON 顶层必须是列表（list）。")

    ids = [p.get("id") for p in people]
    if any(i is None for i in ids):
        raise ValueError("每个人都必须有 id。")
    if len(ids) != len(set(ids)):
        raise ValueError("存在重复 id，请检查。")

    id_set = set(ids)

    for p in people:
        sex = p.get("sex", "U")
        if sex not in ["M", "F", "U"]:
            raise ValueError(f"{p['id']} 的 sex 必须是 'M'/'F'/'U'。")

        for key in ["father_id", "mother_id"]:
            val = p.get(key)
            if val and val not in id_set:
                raise ValueError(f"{p['id']} 的 {key}={val} 不存在于列表中。")

# -----------------------------
# 计算代际层级（为了让图更整齐）
# 规则：没有父母记录的人 -> 第0代（祖辈层）
# 子女代 = max(父代,母代) + 1
# -----------------------------
def compute_generations(people):
    person_map = {p["id"]: p for p in people}
    gen = {}

    def get_gen(pid, visiting=None):
        if pid in gen:
            return gen[pid]
        if visiting is None:
            visiting = set()
        if pid in visiting:
            # 防循环（异常数据）
            return 0
        visiting.add(pid)

        p = person_map[pid]
        fid = p.get("father_id")
        mid = p.get("mother_id")

        if not fid and not mid:
            g = 0
        else:
            parent_gens = []
            if fid and fid in person_map:
                parent_gens.append(get_gen(fid, visiting))
            if mid and mid in person_map:
                parent_gens.append(get_gen(mid, visiting))
            g = (max(parent_gens) + 1) if parent_gens else 0

        gen[pid] = g
        visiting.remove(pid)
        return g

    for pid in person_map:
        get_gen(pid)

    return gen

# -----------------------------
# 画图函数（纯绘图，不推理）
# -----------------------------
def draw_pedigree(people, title="Pedigree", rankdir="TB", show_labels=True):
    validate_people(people)

    dot = Digraph("Pedigree")
    dot.attr(label=title, labelloc="t", fontsize="20")
    dot.attr(rankdir=rankdir, splines="line", nodesep="0.55", ranksep="0.8")
    dot.attr("node", fontname="Arial", fontsize="10")
    dot.attr("edge", dir="none", penwidth="1.2")

    generations = compute_generations(people)

    # 1) 人物节点
    for p in people:
        pid = p["id"]
        name = p.get("name", pid)
        sex = p.get("sex", "U")
        affected = bool(p.get("affected", False))
        proband = bool(p.get("proband", False))

        if sex == "M":
            shape = "box"
        elif sex == "F":
            shape = "circle"
        else:
            shape = "diamond"

        fillcolor = "black" if affected else "white"
        penwidth = "2.8" if proband else "1.5"
        xlabel = name if show_labels else ""

        dot.node(
            pid,
            label="",
            xlabel=xlabel,
            shape=shape,
            width="0.5",
            height="0.5",
            fixedsize="true",
            style="filled",
            fillcolor=fillcolor,
            color="black",
            penwidth=penwidth
        )

    # 2) 家庭单元（共同父母 -> 一组子女）
    families = {}
    for p in people:
        fid = p.get("father_id")
        mid = p.get("mother_id")
        if fid and mid:
            families.setdefault((fid, mid), []).append(p["id"])

    # 3) 画夫妻线 + 子代线
    for i, ((fid, mid), children) in enumerate(families.items(), start=1):
        marr = f"_MARR_{i}"
        sib = f"_SIB_{i}"

        dot.node(marr, label="", shape="point", width="0.01")
        dot.node(sib, label="", shape="point", width="0.01")

        dot.edge(fid, marr)
        dot.edge(marr, mid)
        dot.edge(marr, sib)

        for cid in children:
            dot.edge(sib, cid)

        # 父母同层
        with dot.subgraph() as s:
            s.attr(rank="same")
            s.node(fid)
            s.node(mid)

        # 子女同层（尽量）
        with dot.subgraph() as s2:
            s2.attr(rank="same")
            for cid in children:
                s2.node(cid)

    # 4) 强制整代同层（让祖辈/父母辈/子代更整齐）
    gen_to_ids = {}
    for p in people:
        pid = p["id"]
        g = generations[pid]
        gen_to_ids.setdefault(g, []).append(pid)

    for g, ids_in_gen in gen_to_ids.items():
        with dot.subgraph(name=f"cluster_gen_{g}") as sg:
            sg.attr(color="white")
            sg.attr(rank="same")
            for pid in ids_in_gen:
                sg.node(pid)

    return dot

# -----------------------------
# 页面 UI（纯绘图版）
# -----------------------------
st.title("家系图绘制器（纯事实版）")
st.caption("只根据你输入的事实画图，不做风险评估、不做推理。")

with st.expander("JSON 输入格式示例（可直接复制修改）", expanded=False):
    st.code(DEFAULT_JSON, language="json")

json_text = st.text_area(
    "在这里粘贴/编辑家族史 JSON",
    value=DEFAULT_JSON,
    height=360
)

col1, col2, col3 = st.columns([1.1, 1, 1])

with col1:
    graph_title = st.text_input("图标题", value="Pedigree Demo")
with col2:
    rankdir = st.selectbox("布局方向", ["TB", "LR"], index=0)
with col3:
    show_labels = st.checkbox("显示姓名标签", value=True)

run_btn = st.button("生成家系图", type="primary")

if run_btn:
    try:
        people = json.loads(json_text)
        dot = draw_pedigree(
            people=people,
            title=graph_title,
            rankdir=rankdir,
            show_labels=show_labels
        )

        st.subheader("生成结果")

        # 主显示（Graphviz）
        try:
            st.graphviz_chart(dot.source, use_container_width=True)
        except Exception as e:
            st.warning(f"图形显示失败（可能是云端 Graphviz 渲染兼容问题）：{e}")

        # 备用：显示 DOT 源码，至少能确认生成成功
        with st.expander("查看 Graphviz DOT 源码（如果图没显示，可先看这个）", expanded=False):
            st.code(dot.source, language="dot")

        st.success("已根据事实生成家系图（无推理版）。")

    except json.JSONDecodeError as e:
        st.error(f"JSON 格式错误：{e}")
    except Exception as e:
        st.error(f"运行失败：{e}")

# -----------------------------
# 使用说明（放底部）
# -----------------------------
with st.expander("字段说明", expanded=False):
    st.markdown(
        """
- `id`：唯一编号（不能重复）
- `name`：显示名字（可写“父亲”“母亲”“患者”等）
- `sex`：`"M"` 男，`"F"` 女，`"U"` 不明
- `affected`：`true`（患病，实心）/ `false`（未患病，空心）
- `father_id`：父亲编号（可选）
- `mother_id`：母亲编号（可选）
- `proband`：是否为患者/先证者（可选，`true` 时边框加粗）
        """
    )
