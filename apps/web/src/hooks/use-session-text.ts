"use client";
import { useEffect, useState } from "react";

export function useSessionText(key: string, maxLength: number) {
  const [entry, setEntry] = useState({ key, value: "" });
  const [notice, setNotice] = useState("");
  useEffect(() => {
    try {
      const value = sessionStorage.getItem(key)?.slice(0, maxLength) || "";
      setEntry({ key, value });
      setNotice(value ? "已恢复本页暂存的修改意见；尚未提交生成。" : "");
    } catch { setEntry({ key, value: "" }); setNotice("浏览器暂存不可用，请先复制保留修改意见。"); }
  }, [key, maxLength]);
  function update(value: string) {
    value = value.slice(0, maxLength);
    setEntry({ key, value });
    try {
      if (value) sessionStorage.setItem(key, value); else sessionStorage.removeItem(key);
      setNotice(value ? "修改意见已暂存于当前标签页，刷新后可恢复。" : "");
    } catch { setNotice("浏览器暂存不可用，请先复制保留修改意见。"); }
  }
  return { value: entry.key === key ? entry.value : "", update, notice };
}
