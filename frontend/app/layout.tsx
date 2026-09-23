import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Debate Arena",
  description: "结构化论辩练习：断言台账 + 矛盾检测 + 透明谬误标注",
};

// 顶栏右侧的 BadgeBar 是五类降级/提示角标的唯一挂载点；降级必须可见，缺角标即视为缺陷
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-white text-neutral-900">{children}</body>
    </html>
  );
}
