import { motion } from 'framer-motion';
import {
  FileText,
  MessageSquare,
  Lightbulb,
  Check,
  X,
  Users,
  CheckCircle2,
  Circle,
  Clock,
  User,
  Calendar,
  ChevronDown,
  ListTodo,
  Command,
} from 'lucide-react';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.2 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

/* ─── Mock Decision Status Badge ─── */
function StatusBadge({
  status,
  label,
}: {
  status: 'approved' | 'latest' | 'draft';
  label: string;
}) {
  const styles = {
    approved: 'bg-green-500/20 text-green-300 border-green-500/30',
    latest: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    draft: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  };
  return (
    <span
      className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${styles[status]}`}
    >
      {label}
    </span>
  );
}

/* ─── Mock Minutes View ─── */
function MockMinutesView() {
  return (
    <div className="glass-card rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-mit-primary" />
          <div>
            <h3 className="text-sm font-semibold text-white">
              Q1 스프린트 기획 회의
            </h3>
            <p className="text-xs text-white/40">
              2025년 1월 15일 · 참여자 5명
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">3 agendas</span>
          <span className="text-xs text-white/40">·</span>
          <span className="text-xs text-white/40">5 decisions</span>
        </div>
      </div>

      {/* Summary */}
      <div className="px-6 py-4 border-b border-white/10">
        <p className="text-sm text-white/60 leading-relaxed">
          Q1 로드맵의 핵심 방향성을 논의하고, 디자인 시스템 v2 마이그레이션 일정
          및 성능 최적화 스프린트 계획을 확정했습니다.
        </p>
      </div>

      {/* Agenda #1 */}
      <div className="px-6 py-5 border-b border-white/10">
        <h4 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <span className="text-mit-primary">#1</span> API 리팩토링 방향
        </h4>

        {/* Decision Card — Approved */}
        <div className="rounded-xl border border-white/10 bg-white/[0.03] overflow-hidden">
          <div className="p-4 border-b border-white/10">
            <div className="flex items-center gap-2 mb-2">
              <StatusBadge status="approved" label="Approved" />
              <div className="flex items-center gap-1 text-xs text-white/50">
                <Users className="w-3 h-3" />
                <span>3 approved / 0 rejected</span>
              </div>
            </div>
            <p className="text-sm text-white font-medium">
              REST API를 GraphQL로 점진적 마이그레이션. 신규 엔드포인트부터 적용하고, 기존 API는 Q2까지 유지.
            </p>
          </div>
          <div className="px-4 py-2 flex items-center justify-between bg-white/[0.02]">
            <div className="flex items-center gap-4 text-xs text-white/50">
              <span className="flex items-center gap-1">
                <MessageSquare className="w-3.5 h-3.5" />3 comments
              </span>
              <span className="flex items-center gap-1">
                <Lightbulb className="w-3.5 h-3.5" />1 suggestion
              </span>
            </div>
            <ChevronDown className="w-4 h-4 text-white/30" />
          </div>
        </div>
      </div>

      {/* Agenda #2 */}
      <div className="px-6 py-5 border-b border-white/10">
        <h4 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <span className="text-mit-primary">#2</span> 디자인 시스템 마이그레이션
        </h4>

        {/* Decision Card — Latest (active review) */}
        <div className="rounded-xl border border-white/10 bg-white/[0.03] overflow-hidden">
          <div className="p-4 border-b border-white/10">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <StatusBadge status="latest" label="Latest" />
                  <div className="flex items-center gap-1 text-xs text-white/50">
                    <Users className="w-3 h-3" />
                    <span>2 approved / 1 rejected</span>
                  </div>
                </div>
                <p className="text-sm text-white font-medium">
                  디자인 시스템 v2를 Tailwind 기반으로 전환. 컴포넌트 라이브러리는 shadcn/ui 패턴을 따른다.
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-green-300 bg-green-500/20 border border-green-500/30 rounded-lg">
                  <Check className="w-3.5 h-3.5" />
                  Approve
                </span>
                <span className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-red-300 bg-red-500/20 border border-red-500/30 rounded-lg">
                  <X className="w-3.5 h-3.5" />
                  Reject
                </span>
              </div>
            </div>
          </div>

          {/* Expanded: Comment thread */}
          <div className="p-4 space-y-3 bg-white/[0.01]">
            {/* User Comment */}
            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-full bg-sky-500/20 border border-sky-400/20 flex items-center justify-center flex-shrink-0">
                <span className="text-[10px] text-sky-300">김</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-medium text-white/80">
                    김개발
                  </span>
                  <span className="text-[10px] text-white/30">2분 전</span>
                </div>
                <p className="text-xs text-white/60">
                  shadcn/ui 도입은 좋은데 기존 컴포넌트 호환성은 어떻게 하죠?
                </p>
              </div>
            </div>

            {/* AI Reply */}
            <div className="flex items-start gap-2.5 ml-8">
              <img
                src="/agent.png"
                alt="부덕이"
                className="w-7 h-7 rounded-full flex-shrink-0"
              />
              <div className="flex-1 bg-gradient-to-br from-mit-purple/10 to-purple-600/5 border border-purple-400/15 rounded-lg px-3 py-2">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-medium text-purple-300">
                    부덕이
                  </span>
                  <span className="text-[10px] bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded-full">
                    AI
                  </span>
                </div>
                <p className="text-xs text-white/60">
                  기존 컴포넌트는 어댑터 패턴으로 래핑하면 점진적 전환이 가능합니다. 1차 회의(12/20)에서도 동일한 방안이 논의되었습니다.
                </p>
              </div>
            </div>

            {/* Unified Input */}
            <div className="mt-2 flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2 border border-white/[0.06]">
              <span className="text-white/30 text-xs">Comment</span>
              <span className="text-white/15">|</span>
              <span className="text-white/20 text-xs">
                의견을 입력하세요...
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Action Items */}
      <div className="px-6 py-5">
        <h4 className="text-base font-bold text-white mb-4 flex items-center gap-2">
          <ListTodo className="w-5 h-5 text-mit-primary" />
          Action Items
        </h4>
        <div className="space-y-2">
          {/* Completed */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10">
            <div className="p-1.5 rounded-lg bg-green-500/20">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
            </div>
            <span className="text-sm text-white/40 line-through flex-1">
              GraphQL 스키마 초안 작성
            </span>
            <div className="flex items-center gap-1 text-[11px] text-white/30">
              <User className="w-3 h-3" />
              김개발
            </div>
          </div>
          {/* In Progress */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-colors">
            <div className="p-1.5 rounded-lg bg-blue-500/20">
              <Clock className="w-4 h-4 text-blue-400" />
            </div>
            <span className="text-sm text-white flex-1">
              Tailwind 컴포넌트 마이그레이션 가이드 작성
            </span>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1 text-[11px] text-white/40">
                <User className="w-3 h-3" />
                이디자인
              </div>
              <div className="flex items-center gap-1 text-[11px] text-white/40">
                <Calendar className="w-3 h-3" />
                1월 20일
              </div>
            </div>
          </div>
          {/* Pending */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-colors">
            <div className="p-1.5 rounded-lg bg-white/10">
              <Circle className="w-4 h-4 text-white/50" />
            </div>
            <span className="text-sm text-white flex-1">
              성능 벤치마크 테스트 환경 구축
            </span>
            <div className="flex items-center gap-1 text-[11px] text-white/40">
              <User className="w-3 h-3" />
              박백엔드
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Mock Spotlight Chat ─── */
function MockSpotlightChat() {
  return (
    <div className="glass-card rounded-2xl p-5 overflow-hidden">
      <div className="flex items-center gap-2 mb-4">
        <Command className="w-4 h-4 text-mit-primary" />
        <span className="text-xs font-semibold text-white/50 uppercase tracking-wider">
          Spotlight
        </span>
      </div>

      <div className="space-y-3">
        {/* User */}
        <div className="flex gap-2.5 justify-end">
          <div className="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-br-sm bg-mit-primary/20 border border-mit-primary/30 text-sm text-white/90">
            지난 달 API 관련 결정사항 알려줘
          </div>
        </div>
        {/* AI */}
        <div className="flex gap-2.5">
          <img
            src="/agent.png"
            alt="부덕이"
            className="w-7 h-7 rounded-full flex-shrink-0"
          />
          <div className="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-bl-sm bg-white/5 border border-white/[0.06] text-sm text-white/70 space-y-1.5">
            <p>
              지난 달 API 관련 결정사항은 <strong className="text-white">2건</strong>입니다:
            </p>
            <p>
              1. <strong className="text-white">REST → GraphQL 전환</strong> — Q1 신규 엔드포인트부터 적용 (1/15 회의)
            </p>
            <p>
              2. <strong className="text-white">API 버전관리</strong> — URI 버전닝(v2) 방식 채택 (1/8 회의)
            </p>
          </div>
        </div>
      </div>

      {/* Input Bar — Cmd+K 없이 */}
      <div className="mt-4 glass-input px-5 py-3 flex items-center gap-3 opacity-50">
        <span className="text-white/30 text-sm">{'>'}</span>
        <span className="text-white/30 text-sm">
          Mit에게 무엇이든 물어보세요...
        </span>
      </div>
    </div>
  );
}

/* ─── Main Demo Section ─── */
export function DemoSection() {
  return (
    <section id="demo" className="py-24 sm:py-32 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <p className="text-section-header mb-3">PRODUCT PREVIEW</p>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-3">
            회의 끝나고 5분 후
          </h2>
          <p className="text-white/50 text-base max-w-2xl mx-auto">
            AI가 정리한 회의록, 팀이 함께 리뷰합니다.
          </p>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6"
        >
          {/* Left: Minutes Mock */}
          <motion.div variants={itemVariants}>
            <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 flex items-center gap-2">
              <FileText className="w-3.5 h-3.5" />
              AI 회의록
            </p>
            <MockMinutesView />
          </motion.div>

          {/* Right: Spotlight Chat */}
          <motion.div variants={itemVariants} className="lg:mt-8">
            <p className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Command className="w-3.5 h-3.5" />
              Spotlight 검색
            </p>
            <MockSpotlightChat />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
