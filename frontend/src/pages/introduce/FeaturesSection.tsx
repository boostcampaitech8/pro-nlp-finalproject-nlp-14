import { motion } from 'framer-motion';
import { FEATURES } from './constants';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.15 } },
};

const cardVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

const variantStyles = {
  primary: {
    card: 'bg-gradient-to-br from-mit-primary/20 via-purple-500/15 to-purple-600/5 border-purple-400/25 hover:border-purple-400/40 hover:shadow-[0_16px_48px_rgba(168,85,247,0.2)]',
    icon: 'bg-gradient-to-br from-mit-primary to-mit-purple shadow-[0_0_16px_rgba(168,85,247,0.25)]',
  },
  accent: {
    card: 'bg-gradient-to-br from-sky-500/10 via-cyan-500/5 to-transparent border-sky-400/15 hover:border-sky-400/30 hover:shadow-[0_12px_36px_rgba(56,189,248,0.1)]',
    icon: 'bg-sky-500/15 border border-sky-400/20',
  },
  default: {
    card: 'bg-white/[0.03] border-white/[0.06] hover:bg-purple-500/[0.08] hover:border-purple-400/20',
    icon: 'bg-white/[0.06] border border-white/[0.08]',
  },
  graph: {
    card: 'bg-gradient-to-br from-emerald-500/10 via-teal-500/5 to-transparent border-emerald-400/15 hover:border-emerald-400/30 hover:shadow-[0_12px_36px_rgba(52,211,153,0.1)]',
    icon: 'bg-emerald-500/15 border border-emerald-400/20',
  },
};

// Sound wave animation for the Video card
function SoundWave() {
  return (
    <div className="flex items-end gap-[3px] h-6 mt-4">
      {[0.6, 1, 0.4, 0.8, 0.5, 1, 0.3, 0.7, 0.9, 0.5].map((h, i) => (
        <motion.div
          key={i}
          className="w-[3px] rounded-full bg-gradient-to-t from-mit-primary/40 to-mit-purple/60"
          animate={{ height: [`${h * 24}px`, `${h * 8}px`, `${h * 24}px`] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            delay: i * 0.1,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
}

// Spotlight bar for Command card
function FauxSpotlight() {
  return (
    <div className="mt-4 bg-white/5 rounded-lg px-3 py-2 flex items-center gap-2 border border-white/[0.06]">
      <span className="text-white/30 text-xs">{'>'}</span>
      <span className="text-white/40 text-xs">오늘 결정사항 알려줘...</span>
    </div>
  );
}

// Shimmer text lines for FileText card
function ShimmerLines() {
  return (
    <div className="mt-4 space-y-2">
      {[80, 65, 90, 50].map((w, i) => (
        <div
          key={i}
          className="h-2 rounded-full bg-gradient-to-r from-white/5 via-white/15 to-white/5 animate-shimmer"
          style={{
            width: `${w}%`,
            backgroundSize: '200% 100%',
          }}
        />
      ))}
    </div>
  );
}

// Node-link animation for GitBranch card
function NodeGraph() {
  const nodes = [
    { cx: 20, cy: 30 },
    { cx: 50, cy: 15 },
    { cx: 80, cy: 35 },
    { cx: 35, cy: 55 },
    { cx: 65, cy: 55 },
  ];
  const links = [
    [0, 1],
    [1, 2],
    [0, 3],
    [3, 4],
    [1, 4],
    [2, 4],
  ];

  return (
    <svg
      viewBox="0 0 100 70"
      className="w-full h-16 mt-4"
      fill="none"
    >
      {links.map(([from, to], i) => (
        <motion.line
          key={i}
          x1={nodes[from].cx}
          y1={nodes[from].cy}
          x2={nodes[to].cx}
          y2={nodes[to].cy}
          stroke="rgba(52,211,153,0.2)"
          strokeWidth={1}
          initial={{ pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, delay: i * 0.1 }}
        />
      ))}
      {nodes.map((node, i) => (
        <motion.circle
          key={i}
          cx={node.cx}
          cy={node.cy}
          r={4}
          fill="rgba(52,211,153,0.6)"
          initial={{ scale: 0 }}
          whileInView={{ scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 + i * 0.1, type: 'spring' }}
        />
      ))}
    </svg>
  );
}

const decorationMap: Record<string, () => JSX.Element> = {
  '실시간 AI 회의': SoundWave,
  'Spotlight AI 에이전트': FauxSpotlight,
  '자동 회의록': ShimmerLines,
  '조직 지식 그래프': NodeGraph,
};

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 sm:py-32 px-6">
      <div className="max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <p className="text-section-header mb-3">FEATURES</p>
          <h2 className="text-3xl sm:text-4xl font-bold text-white">
            {FEATURES.headline}
          </h2>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          className="grid grid-cols-1 sm:grid-cols-2 gap-5"
        >
          {FEATURES.cards.map((card, i) => {
            const Icon = card.icon;
            const styles = variantStyles[card.variant];
            const Decoration = decorationMap[card.title];
            return (
              <motion.div
                key={i}
                variants={cardVariants}
                whileHover={{ scale: 1.02, y: -4 }}
                transition={{ duration: 0.3 }}
                className={`relative p-6 rounded-xl backdrop-blur-lg border ${styles.card} transition-all duration-300 group overflow-hidden`}
              >
                {/* Glow sweep overlay */}
                <div className="absolute inset-0 rounded-xl overflow-hidden pointer-events-none">
                  <div className="absolute -inset-full w-[200%] h-[200%] opacity-0 group-hover:animate-[glow-sweep_0.6s_ease-out_forwards] bg-gradient-to-br from-transparent via-purple-400/10 to-transparent" />
                </div>

                <div className="relative">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${styles.icon}`}
                  >
                    <Icon className="w-5 h-5 text-white/80" />
                  </div>
                  <h3 className="text-card-title mb-2">{card.title}</h3>
                  <p className="text-card-desc">{card.description}</p>
                  {Decoration && <Decoration />}
                </div>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
