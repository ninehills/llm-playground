#!/usr/bin/env python
#-*- coding: utf-8 -*-
import os
import streamlit as st

import prompt
from wenxin_llm import Wenxin
from wudao_llm import Wudao
from langchain.llms import OpenAIChat
from langchain.chains import LLMChain

## Environment variables
# Access code, leave it empty if you don't want to use it.
CODE = os.environ.get("CODE", "")

## Global variables
# Prompt 存储
if os.environ.get("CUSTOM_PROMPTS_STORE", "file") == "supabase":
    prompt_store = prompt.Store(custom_prompts_store=prompt.PromptSupabaseStore())
else:
    prompt_store = prompt.Store(custom_prompts_store=prompt.PromptFileStore())

# 模型列表
models = ["GPT-3.5", "GPT-4", "GPT-4-32K", "ChatGLM-130B", "文心千帆"]


@st.cache_data(persist="disk")
def make_request(input: str, model: str, temperature: float, prompt_name: str) -> str:
    """Make a request to the Model."""
    if model == "文心千帆":
        llm = Wenxin(verbose=True)
    elif model == "GPT-3.5":
        llm = OpenAIChat(
            model_name="gpt-3.5-turbo",
            temperature=temperature,
            verbose=True,
        )
    elif model == "GPT-4":
        llm = OpenAIChat(
            model_name="gpt-4",
            temperature=temperature,
            verbose=True,
        )
    elif model == "GPT-4-32K":
        llm = OpenAIChat(
            model_name="gpt-4-32k",
            temperature=temperature,
            verbose=True,
        )
    elif model == "ChatGLM-130B":
        llm = Wudao(
            temperature=temperature,
            verbose=True,
        )
    else:
        raise ValueError(f"Unknown model: {model}")

    p = prompt_store.get(prompt_name)
    if not p:
        raise ValueError(f"Unknown prompt: {prompt_name}")
    chain = LLMChain(
        llm=llm,
        prompt=prompt_store.get(prompt_name),
        verbose=True,
    )

    result = chain({"question": input})["text"]
    return result
    

## From here down is all the StreamLit UI.
st.set_page_config(page_title="LLM Playground", page_icon=":robot:", layout="wide")
st.header("LLM Playground")
st.markdown("""---""")

## Session
if 'page' not in st.session_state:
    # question / list_prompts / add_prompt
    st.session_state.page = 'question'

# Sidebar
with st.sidebar:
    if CODE:
        code = st.text_input("输入访问码", type="password")
        if code != CODE:
            st.error("访问码错误")
            st.stop()

    prompt_name_selected = st.multiselect(
        "选择 Prompt（可多选）",
        prompt_store.list_names(),
    )

    def button_callback():
        if st.session_state.page != 'list_prompts':
            st.session_state.page = 'list_prompts'
        else:
            st.session_state.page = 'question'
    st.button("查看 Prompt", on_click=button_callback)

    model_selected = st.multiselect(
        "选择模型（可多选）",
        models,
        default=["GPT-3.5"],
    )

    temperature = st.slider(
        "模型温度",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1,
    )

    show_prompt = st.checkbox("显示 Prompt", value=False)

    if st.button("清空回答缓存"):
        st.cache_data.clear()

if st.session_state.page =='list_prompts':
    if prompt_store.custom_prompts_store.name == "file":
        st.markdown("自定义提示词后端为文件，如果运行在 streamlit，重启app可能会导致丢失，请及时下载保存。")
    col0, col1 = st.columns(2)
    def add_button_callback():
        st.session_state.page = "add_prompt"
    col0.button("增加自定义提示词", on_click=add_button_callback)

    if prompt_store.custom_prompts_store.name == "file":
        if os.path.exists(prompt.CUSTOM_PROMPTS_FILE):
            with open(prompt.CUSTOM_PROMPTS_FILE, "r") as f:
                col1.download_button("下载自定义提示词", f, prompt.CUSTOM_PROMPTS_FILE, "application/json")

    st.dataframe(prompt_store.data(), use_container_width=True)

if st.session_state.page =='add_prompt':
    with st.form(key="add_prompt"):
        prompt_name = st.text_input("提示词名称")
        prompt_text = st.text_area("提示词内容，问题请用 `{question}` 表示")
        submit_button = st.form_submit_button("提交")

        if submit_button:
            if not prompt_name or not prompt_text:
                st.error("提示词名称和内容不能为空")
            else:
                prompt_store.add(prompt_name, prompt_text)
                st.session_state.page = "list_prompts"
                st.experimental_rerun()

if st.session_state.page == 'question':
    input = st.text_area("输入", placeholder="", label_visibility="hidden")
    run_button = st.button("提交")

    cols = len(prompt_name_selected) * len(model_selected)
    if cols == 0:
        st.warning("请至少选择一个 Prompt")
        st.stop()


    columns = st.columns(cols)
    order = 0
    for model in model_selected:
        for prompt_name in  prompt_name_selected:
            c = columns[order]
            order += 1
            with c.container():
                st.markdown(f"模型：`{model}`  Prompt: `{prompt_name}`")
                if show_prompt:
                    st.markdown("---")
                    st.markdown(f"```\n{prompt_store.get(prompt_name).template}\n```")
                    st.markdown("---")
                if run_button:
                    response = None
                    with st.spinner("正在生成回答..."):
                        try:
                            response = make_request(input, model, temperature, prompt_name)
                        except Exception as e:
                            st.error(f"调用出现异常，错误信息: {e}")
                    if response:
                        st.markdown(response)
                    else:
                        st.error("调用失败，请重试")
                else:
                    pass


