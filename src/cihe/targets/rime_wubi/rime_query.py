"""用 librime 的 C API 在部署后的方案上查码，验证运行期候选与 OpenCC 输出。

`rime_deployer --compile` 只验证编译产物；这里创建真实 Rime 会话，按码取候选，
因此能覆盖 `wubi_trad` 的 OpenCC simplifier 输出。仅支持装有 `rime_get_api`
的 librime（Debian 的 `librime-bin` 满足）。
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from cihe.dicts import read_char_table
from cihe.targets.rime_wubi.rime import SCHEMA_IDS, DeployResult


class RimeQueryError(RuntimeError):
    """librime 会话或查码失败。"""


@dataclass(frozen=True)
class SchemaQuery:
    schema_id: str
    codes: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenccCheck:
    ok: bool
    word: str = ""
    code: str = ""
    expected: str = ""
    converted: str = ""
    simplified: list[str] = field(default_factory=list)
    traditional: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(frozen=True)
class QueryResult:
    schemas: dict[str, SchemaQuery]
    opencc: OpenccCheck
    version: str


# 常见的、无歧义的单字简繁映射；不用有歧义的 发/髮、里/裡、面/麵。
S2T_PAIRS = {
    "语": "語",
    "学": "學",
    "国": "國",
    "汉": "漢",
    "车": "車",
    "门": "門",
    "马": "馬",
    "书": "書",
    "长": "長",
    "时": "時",
    "间": "間",
    "会": "會",
    "万": "萬",
    "与": "與",
    "为": "為",
    "从": "從",
    "东": "東",
    "乐": "樂",
    "业": "業",
    "个": "個",
    "来": "來",
    "师": "師",
    "军": "軍",
    "农": "農",
    "医": "醫",
    "药": "藥",
    "电": "電",
    "话": "話",
    "买": "買",
    "卖": "賣",
}

# 有歧义或不在映射里的字不用于 OpenCC 断言；只要求选出的词至少有一个可转换字。
_AMBIGUOUS = frozenset("发里面干后只台几系松卷云")


def _traditional(word: str) -> str:
    return "".join(S2T_PAIRS.get(character, character) for character in word)


def _opencc_candidates(
    entries: Sequence[tuple[str, str]], limit: int = 8
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for word, code in entries:
        if any(character in _AMBIGUOUS for character in word):
            continue
        if not any(character in S2T_PAIRS for character in word):
            continue
        if _traditional(word) == word:
            continue
        candidates.append((word, code))
        if len(candidates) >= limit:
            break
    return candidates


# ---- librime C API -------------------------------------------------


c_int = ctypes.c_int
_c_char_p = ctypes.c_char_p
_c_void_p = ctypes.c_void_p
_c_size_t = ctypes.c_size_t
_Bool = c_int
_RimeSessionId = ctypes.c_size_t


class _RimeTraits(ctypes.Structure):
    _fields_ = [
        ("data_size", c_int),
        ("shared_data_dir", _c_char_p),
        ("user_data_dir", _c_char_p),
        ("distribution_name", _c_char_p),
        ("distribution_code_name", _c_char_p),
        ("distribution_version", _c_char_p),
        ("app_name", _c_char_p),
        ("modules", ctypes.POINTER(_c_char_p)),
        ("min_log_level", c_int),
        ("log_dir", _c_char_p),
        ("prebuilt_data_dir", _c_char_p),
        ("staging_dir", _c_char_p),
    ]


class _RimeCandidate(ctypes.Structure):
    _fields_ = [
        ("text", _c_char_p),
        ("comment", _c_char_p),
        ("reserved", _c_void_p),
    ]


class _RimeCandidateListIterator(ctypes.Structure):
    _fields_ = [
        ("ptr", _c_void_p),
        ("index", c_int),
        ("candidate", _RimeCandidate),
    ]


class _RimeApi(ctypes.Structure):
    # 只声明到 candidate_list_end；前面的字段顺序必须与 rime_api.h 完全一致。
    _fields_ = [
        ("data_size", c_int),
        ("setup", _c_void_p),
        ("set_notification_handler", _c_void_p),
        ("initialize", _c_void_p),
        ("finalize", _c_void_p),
        ("start_maintenance", _c_void_p),
        ("is_maintenance_mode", _c_void_p),
        ("join_maintenance_thread", _c_void_p),
        ("deployer_initialize", _c_void_p),
        ("prebuild", _c_void_p),
        ("deploy", _c_void_p),
        ("deploy_schema", _c_void_p),
        ("deploy_config_file", _c_void_p),
        ("sync_user_data", _c_void_p),
        ("create_session", _c_void_p),
        ("find_session", _c_void_p),
        ("destroy_session", _c_void_p),
        ("cleanup_stale_sessions", _c_void_p),
        ("cleanup_all_sessions", _c_void_p),
        ("process_key", _c_void_p),
        ("commit_composition", _c_void_p),
        ("clear_composition", _c_void_p),
        ("get_commit", _c_void_p),
        ("free_commit", _c_void_p),
        ("get_context", _c_void_p),
        ("free_context", _c_void_p),
        ("get_status", _c_void_p),
        ("free_status", _c_void_p),
        ("set_option", _c_void_p),
        ("get_option", _c_void_p),
        ("set_property", _c_void_p),
        ("get_property", _c_void_p),
        ("get_schema_list", _c_void_p),
        ("free_schema_list", _c_void_p),
        ("get_current_schema", _c_void_p),
        ("select_schema", _c_void_p),
        ("schema_open", _c_void_p),
        ("config_open", _c_void_p),
        ("config_close", _c_void_p),
        ("config_get_bool", _c_void_p),
        ("config_get_int", _c_void_p),
        ("config_get_double", _c_void_p),
        ("config_get_string", _c_void_p),
        ("config_get_cstring", _c_void_p),
        ("config_update_signature", _c_void_p),
        ("config_begin_map", _c_void_p),
        ("config_next", _c_void_p),
        ("config_end", _c_void_p),
        ("simulate_key_sequence", _c_void_p),
        ("register_module", _c_void_p),
        ("find_module", _c_void_p),
        ("run_task", _c_void_p),
        ("get_shared_data_dir", _c_void_p),
        ("get_user_data_dir", _c_void_p),
        ("get_sync_dir", _c_void_p),
        ("get_user_id", _c_void_p),
        ("get_user_data_sync_dir", _c_void_p),
        ("config_init", _c_void_p),
        ("config_load_string", _c_void_p),
        ("config_set_bool", _c_void_p),
        ("config_set_int", _c_void_p),
        ("config_set_double", _c_void_p),
        ("config_set_string", _c_void_p),
        ("config_get_item", _c_void_p),
        ("config_set_item", _c_void_p),
        ("config_clear", _c_void_p),
        ("config_create_list", _c_void_p),
        ("config_create_map", _c_void_p),
        ("config_list_size", _c_void_p),
        ("config_begin_list", _c_void_p),
        ("get_input", _c_void_p),
        ("get_caret_pos", _c_void_p),
        ("select_candidate", _c_void_p),
        ("get_version", _c_void_p),
        ("set_caret_pos", _c_void_p),
        ("select_candidate_on_current_page", _c_void_p),
        ("candidate_list_begin", _c_void_p),
        ("candidate_list_next", _c_void_p),
        ("candidate_list_end", _c_void_p),
    ]


class _Session:
    def __init__(self, work_dir: Path) -> None:
        try:
            self._lib = ctypes.CDLL("librime.so.1")
        except OSError as error:
            raise RimeQueryError(f"找不到 librime：{error}") from error
        get_api = self._lib.rime_get_api
        get_api.restype = ctypes.POINTER(_RimeApi)
        self._api: Any = get_api().contents
        if self._api.data_size <= 0:
            raise RimeQueryError("librime 的 rime_get_api 返回空结构")

        traits = _RimeTraits()
        traits.data_size = ctypes.sizeof(_RimeTraits) - ctypes.sizeof(c_int)
        traits.shared_data_dir = str(work_dir / "shared").encode()
        traits.user_data_dir = str(work_dir / "user").encode()
        traits.distribution_name = b"cihe"
        traits.distribution_code_name = b"cihe"
        traits.distribution_version = b"1.0"
        traits.app_name = b"rime.cihe"
        traits.min_log_level = 3
        traits.log_dir = b""
        traits.prebuilt_data_dir = str(work_dir / "build").encode()
        traits.staging_dir = str(work_dir / "build").encode()

        self._setup = ctypes.CFUNCTYPE(
            None, ctypes.POINTER(_RimeTraits)
        )(self._api.setup)
        self._initialize = ctypes.CFUNCTYPE(
            None, ctypes.POINTER(_RimeTraits)
        )(self._api.initialize)
        self._finalize = ctypes.CFUNCTYPE(None)(self._api.finalize)
        self._create_session = ctypes.CFUNCTYPE(_RimeSessionId)(
            self._api.create_session
        )
        self._destroy_session = ctypes.CFUNCTYPE(
            _Bool, _RimeSessionId
        )(self._api.destroy_session)
        self._select_schema = ctypes.CFUNCTYPE(
            _Bool, _RimeSessionId, _c_char_p
        )(self._api.select_schema)
        self._simulate = ctypes.CFUNCTYPE(
            _Bool, _RimeSessionId, _c_char_p
        )(self._api.simulate_key_sequence)
        self._clear = ctypes.CFUNCTYPE(None, _RimeSessionId)(
            self._api.clear_composition
        )
        self._candidate_begin = ctypes.CFUNCTYPE(
            _Bool, _RimeSessionId, ctypes.POINTER(_RimeCandidateListIterator)
        )(self._api.candidate_list_begin)
        self._candidate_next = ctypes.CFUNCTYPE(
            _Bool, ctypes.POINTER(_RimeCandidateListIterator)
        )(self._api.candidate_list_next)
        self._candidate_end = ctypes.CFUNCTYPE(
            None, ctypes.POINTER(_RimeCandidateListIterator)
        )(self._api.candidate_list_end)
        get_version = ctypes.CFUNCTYPE(_c_char_p)(self._api.get_version)

        self._traits = traits
        self._setup(ctypes.byref(traits))
        self._initialize(ctypes.byref(traits))
        self.version = (get_version() or b"").decode("utf-8")
        self.session_id = self._create_session()
        if not self.session_id:
            self._finalize()
            raise RimeQueryError("librime 无法创建会话")

    def close(self) -> None:
        if getattr(self, "session_id", None):
            self._destroy_session(self.session_id)
            self.session_id = 0
        self._finalize()

    def candidates(self, schema_id: str, code: str) -> list[str]:
        if not self._select_schema(self.session_id, schema_id.encode()):
            raise RimeQueryError(f"无法选择 schema：{schema_id}")
        self._clear(self.session_id)
        if not self._simulate(self.session_id, code.encode()):
            raise RimeQueryError(f"无法模拟按键：{schema_id}/{code}")
        iterator = _RimeCandidateListIterator()
        result: list[str] = []
        if self._candidate_begin(self.session_id, ctypes.byref(iterator)):
            try:
                while self._candidate_next(ctypes.byref(iterator)):
                    text = iterator.candidate.text
                    if text:
                        result.append(text.decode("utf-8"))
            finally:
                self._candidate_end(ctypes.byref(iterator))
        self._clear(self.session_id)
        return result


def _sample_codes(entries: Sequence[tuple[str, str]], limit: int) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for _text, code in entries:
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
        if len(codes) >= limit:
            break
    return codes


def _words_by_code(entries: Sequence[tuple[str, str]]) -> dict[str, list[str]]:
    words: dict[str, list[str]] = {}
    for text, code in entries:
        words.setdefault(code, []).append(text)
    return words


def query_package(
    deployed: DeployResult,
    package_dir: Path,
    *,
    code_limit: int = 3,
) -> QueryResult:
    """在已部署的方案上查码；wubi_trad 额外断言 OpenCC 转换结果。"""
    char_entries = read_char_table(package_dir / "wubi86.zi.dict.yaml")
    word_entries: list[tuple[str, str]] = []
    for name in package_dir.glob("wubi86.ci.*.dict.yaml"):
        word_entries.extend(read_char_table(name))
    entries = word_entries + char_entries
    by_code = _words_by_code(entries)
    codes = _sample_codes(entries, code_limit * 2)

    work_dir = deployed.table_path.parent.parent
    session = _Session(work_dir)
    try:
        schemas: dict[str, SchemaQuery] = {}
        for schema_id in SCHEMA_IDS:
            if schema_id not in deployed.schemas:
                raise RimeQueryError(f"部署结果缺少 schema：{schema_id}")
            checked: dict[str, list[str]] = {}
            for code in codes:
                candidates = session.candidates(schema_id, code)
                if not candidates:
                    continue
                if schema_id != "wubi_trad":
                    expected = by_code.get(code, [])
                    if not set(candidates) & set(expected):
                        continue
                checked[code] = candidates
                if len(checked) >= code_limit:
                    break
            if len(checked) < code_limit:
                raise RimeQueryError(
                    f"{schema_id} 只查到 {len(checked)} 个可用码，"
                    f"要求 {code_limit}"
                )
            schemas[schema_id] = SchemaQuery(
                schema_id=schema_id, codes=checked
            )

        selections = _opencc_candidates(word_entries) or _opencc_candidates(
            char_entries
        )
        opencc = OpenccCheck(
            ok=False, reason="包内没有可用于 OpenCC 断言的词条"
        )
        for word, code in selections:
            expected = _traditional(word)
            mapped = [
                S2T_PAIRS[character]
                for character in word
                if character in S2T_PAIRS
            ]
            simplified = session.candidates("wubi86", code)
            traditional = session.candidates("wubi_trad", code)
            converted = [
                candidate
                for candidate in traditional
                if candidate != word
                and all(character in candidate for character in mapped)
            ]
            if converted:
                opencc = OpenccCheck(
                    ok=True,
                    word=word,
                    code=code,
                    expected=expected,
                    converted=converted[0],
                    simplified=simplified,
                    traditional=traditional,
                )
                break
            if opencc.reason == "包内没有可用于 OpenCC 断言的词条":
                opencc = OpenccCheck(
                    ok=False,
                    word=word,
                    code=code,
                    expected=expected,
                    simplified=simplified,
                    traditional=traditional,
                    reason="繁体候选缺失",
                )
        return QueryResult(
            schemas=schemas, opencc=opencc, version=session.version
        )
    finally:
        session.close()
