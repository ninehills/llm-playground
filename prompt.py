#!/usr/bin/env python
#-*- coding: utf-8 -*-
import json
from typing import Dict, List, Optional, Tuple
from langchain.prompts.prompt import PromptTemplate
import pandas as pd
from threading import Lock
import os
import supabase

SYSTEM = "system"
CUSTOM = "custom"

CUSTOM_PROMPTS_FILE = "custom_prompts.json"

class PromptStore(object):
    pass


class PromptFileStore(PromptStore):
    custom_prompts_file = ""
    write_lock = Lock()

    def __init__(self, custom_prompts_file=CUSTOM_PROMPTS_FILE):
        self.custom_prompts_file = custom_prompts_file

    def loads(self) -> Dict[str, Tuple[str, PromptTemplate]]:
        prompts = {}
        try:
            with open(self.custom_prompts_file, "r") as f:
                r = json.load(f)
                for k, v in r.items():
                    prompts[k] = (CUSTOM, PromptTemplate(
                        template=v['template'],
                        input_variables=v['input_variables'],
                    ))
        except Exception:
            pass
        return prompts
    
    def add(self, name, prompt):
        try:
            self.write_lock.acquire()
            return self._add(name, prompt)
        finally:
            self.write_lock.release()

    def _add(self, name, prompt):
        prompts = self.loads()
        prompts[name] = dict(template=prompt.template, input_variables=prompt.input_variables)
        with open(self.custom_prompts_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(prompts, ensure_ascii=False, indent=4))

    @property
    def name(self):
        return "file"

class PromptSupabaseStore(PromptStore):
    def __init__(self, supabase_url=None, supabase_key=None):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_KEY")
    
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Please provide supabase url and key")
        
        self.supabase_client = supabase.create_client(self.supabase_url, self.supabase_key)

    def loads(self) -> Dict[str, Tuple[str, PromptTemplate]]:
        rows = self.supabase_client.table("prompts").select("*").execute()
        print(f"> load supabase prompts: {rows}")
        prompts = {}
        for row in rows.data:
            prompts[row["name"]] = (CUSTOM, PromptTemplate(
                template=row["prompt"]["template"],
                input_variables=row["prompt"]["input_variables"],
            ))
        return prompts

    def add(self, name, prompt):
        self.supabase_client.table("prompts").upsert([
            {
                "name": name,
                "prompt": {
                    "template": prompt.template,
                    "input_variables": prompt.input_variables,
                },
            }
        ]).execute()
        print(f"> add supabase prompt: {name} {prompt}")
    
    @property
    def name(self):
        return "supabase"

class Store(object):
    # Loaded prompts
    # {
    #   "prompt_name": ("system", PromptTemplate),
    #   "custom_prompt_name": ("custom", PromptTemplate),
    # }
    prompts: Dict[str, Tuple[str, PromptTemplate]]= {}
    _prompts_lock = Lock()

    def __init__(
            self,
            prompts_file="prompts.json",
            custom_prompts_store: PromptStore = None,
            ):
        """Initialize the prompt store."""
        self.prompts_file = prompts_file
        self.custom_prompts_store = custom_prompts_store
        self.prompts = {}
        self.load()
    
    def load(self):
        """Load the prompt store from the file."""
        try:
            self._prompts_lock.acquire()
            return self._load()
        finally:
            self._prompts_lock.release()
    
    def _load(self):
        prompts = {}
        with open(self.prompts_file, "r") as f:
            r = json.load(f)
            for k, v in r.items():
                prompts[k] = (SYSTEM, PromptTemplate(
                    template=v['template'],
                    input_variables=v['input_variables'],
                ))
        try:
            custom_prompts = self.custom_prompts_store.loads()
            prompts.update(custom_prompts)
        except Exception as e:
            print(f"load custom prompts failed: {e}")
            return

        self.prompts = prompts


    def get(self, prompt_name: str) -> Optional[PromptTemplate]:
        """Get a prompt by name."""
        if prompt_name in self.prompts:
            return self.prompts[prompt_name][1]
        return None
    
    def list_names(self) -> List[str]:
        """List all prompt names sorted by name."""
        return sorted(
            list(self.prompts.keys()),
            key=lambda x: x.lower(),
        )

    def data(self) -> pd.DataFrame:
        """Return a dataframe of all prompts."""
        return pd.DataFrame(
            [
                {
                    "name": k,
                    "type": v[0],
                    "template": v[1].template,
                    "input_variables": v[1].input_variables,
                }
                for k, v in self.prompts.items()
            ]
        )

    def add(self, prompt_name: str, prompt_template: str):
        """Add a custom prompt."""
        self.custom_prompts_store.add(prompt_name, PromptTemplate(
            template=prompt_template,
            input_variables=["question"],
        ))
        self.load()
