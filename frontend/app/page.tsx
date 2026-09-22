import BadgeBar from "../components/BadgeBar";
import DebateModeSwitch from "../components/DebateModeSwitch";
import DebateStream from "../components/DebateStream";
import DifficultySwitch from "../components/DifficultySwitch";
import FactCheckPanel from "../components/FactCheckPanel";
import FallacyPanel from "../components/FallacyPanel";
import LedgerPanel from "../components/LedgerPanel";
import StrictnessSwitch from "../components/StrictnessSwitch";
import TopicPicker from "../components/TopicPicker";
import UsagePanel from "../components/UsagePanel";

/**
 * 骨架页：只把 §8.2 的组件摆到 §8.1 视觉稿的位置，全部子组件当前返回 null。
 * 归属 P1（DebateStream 有真实流式渲染）→ P2（LedgerPanel）→ P3（FactCheckPanel）→ P4（FallacyPanel）。
 */
export default function Page() {
  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-3 border-b px-4 py-2">
        <TopicPicker />
        <div className="ml-auto flex items-center gap-3">
          <DifficultySwitch />
          <StrictnessSwitch />
          <DebateModeSwitch />
          <UsagePanel />
          <BadgeBar />
        </div>
      </header>
      <main className="flex min-h-0 flex-1">
        <section className="min-w-0 flex-1">
          <DebateStream />
        </section>
        <aside className="w-80 shrink-0 overflow-y-auto border-l">
          <LedgerPanel />
          <FactCheckPanel />
          <FallacyPanel />
        </aside>
      </main>
    </div>
  );
}
