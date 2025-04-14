import streamlit as st
import pandas as pd
import itertools
from io import BytesIO
from tabulate import tabulate

# Инициализация session_state
if "elements" not in st.session_state:
    st.session_state.elements = {}
if "dependencies" not in st.session_state:
    st.session_state.dependencies = {}

st.set_page_config(page_title="Конфигуратор сценариев", layout="wide")
st.title("🧪 Визуальный генератор тестовых сценариев")


# ---------------- ЭТАП 1 ----------------
st.header("1️⃣ Добавление элементов (радиокнопок и значений)")

with st.form("add_element_form", clear_on_submit=True):
    key = st.text_input("Имя элемента", placeholder="например: has_pet")
    values = st.text_input("Значения через запятую", placeholder="например: yes, no")
    submitted = st.form_submit_button("➕ Добавить элемент")

    if submitted:
        if key and values:
            value_list = [v.strip() for v in values.split(",")]
            st.session_state.elements[key] = value_list
            st.success(f"Элемент `{key}` добавлен: {value_list}")
        else:
            st.warning("Заполните оба поля!")


if st.session_state.elements:
    st.markdown("### 📋 Текущие элементы:")
    for k, v in st.session_state.elements.items():
        st.write(f"🔹 **{k}**: {v}")
else:
    st.info("Пока нет элементов. Добавь хотя бы один, чтобы перейти к зависимостям.")

# ---------------- ЭТАП 2 ----------------
if st.session_state.elements:
    st.header("2️⃣ Настройка зависимостей между элементами")

    all_fields = list(st.session_state.elements.keys())

    # Храним предыдущее значение поля, чтобы при изменении — перезапустить интерфейс
    if "target_field_value" not in st.session_state:
        st.session_state.target_field_value = all_fields[0] if all_fields else None

    # Выбор зависимого поля (target)
    target_field = st.selectbox(
        "🧷 Какое поле зависит от других?",
        options=all_fields,
        key="target_field_select"
    )

    # Если поле изменилось — обновляем состояние и перерисовываем
    if target_field != st.session_state.target_field_value:
        st.session_state.target_field_value = target_field
        st.rerun()

    # Формируем список source-полей (без выбранного target)
    source_options = [f for f in all_fields if f != target_field]

    # Только если остались другие поля, показываем форму
    if source_options:
        with st.form("add_dependency_form"):
            source_field = st.selectbox(
                "📍 От какого поля зависит",
                options=source_options,
                key="source_field_select"
            )

            source_value = st.selectbox(
                "📋 При каком значении",
                options=st.session_state.elements.get(source_field, []),
                key="source_value_select"
            )

            submitted_dep = st.form_submit_button("➕ Добавить зависимость")

            if submitted_dep:
                deps = st.session_state.dependencies.get(target_field, {})
                deps[source_field] = source_value
                st.session_state.dependencies[target_field] = deps
                st.success(f"Поле `{target_field}` зависит от `{source_field} == {source_value}`")
    else:
        st.warning("Нет других полей, от которых можно задать зависимость.")

    # Отображаем текущие зависимости
    if st.session_state.dependencies:
        st.markdown("### 🔗 Заданные зависимости (с возможностью удаления):")

        for target, conditions in list(st.session_state.dependencies.items()):
            for source_field, source_value in list(conditions.items()):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.write(f"🔒 `{target}` видно, если `{source_field} == {source_value}`")
                with col2:
                    if st.button("❌", key=f"delete_{target}_{source_field}"):
                        del st.session_state.dependencies[target][source_field]
                        if not st.session_state.dependencies[target]:  # если больше нет условий
                            del st.session_state.dependencies[target]
                        st.rerun()




# ---------------- ЭТАП 3 ----------------
st.header("3️⃣ Генерация сценариев и экспорт")


def is_visible(field, selected, dependencies):
    if field not in dependencies:
        return True
    for dep_field, dep_value in dependencies[field].items():
        if selected.get(dep_field) == dep_value:
            return True  # хоть одно совпало
    return False


# def generate_scenarios(elements, dependencies):
#     scenarios = []
#     keys = list(elements.keys())
#     all_combinations = list(itertools.product(*(elements[k] for k in keys)))

#     for combo in all_combinations:
#         selected = dict(zip(keys, combo))
#         visible_fields = [
#             field for field in keys if is_visible(field, selected, dependencies)
#         ]
#         valid = all(
#             is_visible(k, selected, dependencies) or selected[k] == "" for k in keys
#         )
#         if valid:
#             cleaned_selection = {
#                 k: v if k in visible_fields else "" for k, v in selected.items()
#             }
#             scenarios.append(
#                 {"Выборы": cleaned_selection, "Видимые поля": visible_fields}
#             )
#     return scenarios

def generate_scenarios(elements, dependencies):
    scenarios = []
    seen = set()  # для отслеживания уникальности

    keys = list(elements.keys())
    all_combinations = list(itertools.product(*(elements[k] for k in keys)))

    for combo in all_combinations:
        selected = dict(zip(keys, combo))
        visible_fields = [
            field for field in keys if is_visible(field, selected, dependencies)
        ]
        cleaned_selection = {
            k: v if k in visible_fields else "" for k, v in selected.items()
        }

        # создаем уникальный ключ для сравнения (tuple + frozenset)
        selection_key = tuple((k, cleaned_selection[k]) for k in keys)
        if selection_key not in seen:
            seen.add(selection_key)
            scenarios.append(
                {"Выборы": cleaned_selection, "Видимые поля": visible_fields}
            )

    return scenarios



def scenarios_to_dataframe(scenarios):
    rows = []
    for i, sc in enumerate(scenarios, start=1):
        row = {"Сценарий": i}
        row.update(sc["Выборы"])
        row["Ожидаемые поля на форме"] = ", ".join(sc["Видимые поля"])
        rows.append(row)
    return pd.DataFrame(rows)


def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


def to_txt_string(df):
    return tabulate(df, headers="keys", tablefmt="grid", showindex=False)


if st.button("🚀 Сгенерировать сценарии"):
    try:
        elements = st.session_state.elements
        dependencies = st.session_state.dependencies
        scenarios = generate_scenarios(elements, dependencies)
        df = scenarios_to_dataframe(scenarios)

        st.success(f"✅ Сгенерировано сценариев: {len(df)}")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "📥 Скачать Excel", data=to_excel_bytes(df), file_name="test_scenarios.xlsx"
        )
        st.download_button(
            "📄 Скачать TXT", data=to_txt_string(df), file_name="test_scenarios.txt"
        )

    except Exception as e:
        st.error(f"Ошибка генерации сценариев: {e}")
