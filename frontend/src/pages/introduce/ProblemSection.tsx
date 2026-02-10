import { motion } from 'framer-motion';
import { PROBLEM } from './constants';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.15 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

function ScatteredNotes() {
  const notes = [
    { text: '결정: API 변경', rotate: -6, x: 10, y: 20 },
    { text: '액션아이템: ???', rotate: 3, x: 60, y: 40 },
    { text: '누가 말했더라...', rotate: -2, x: 25, y: 70 },
    { text: '다음 회의 때 다시', rotate: 5, x: 70, y: 15 },
    { text: '회의록.docx (v3)', rotate: -4, x: 45, y: 55 },
  ];

  return (
    <div className="relative w-full h-64 sm:h-80">
      {notes.map((note, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, scale: 0.8 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.1, duration: 0.4 }}
          className="absolute glass-card px-3 py-2 text-xs text-white/50"
          style={{
            left: `${note.x}%`,
            top: `${note.y}%`,
            transform: `rotate(${note.rotate}deg)`,
          }}
        >
          {note.text}
        </motion.div>
      ))}
    </div>
  );
}

export function ProblemSection() {
  return (
    <section id="problem" className="py-24 sm:py-32 px-6">
      <div className="max-w-5xl mx-auto">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.5 }}
          className="text-3xl sm:text-4xl font-bold text-white text-center mb-16"
        >
          {PROBLEM.headline}
        </motion.h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          {/* Left: Scattered Notes */}
          <ScatteredNotes />

          {/* Right: Pain Points */}
          <motion.div
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-100px' }}
            className="space-y-6"
          >
            {PROBLEM.painPoints.map((point, i) => {
              const Icon = point.icon;
              return (
                <motion.div
                  key={i}
                  variants={itemVariants}
                  className="flex items-start gap-4"
                >
                  <div className="icon-container-sm flex-shrink-0">
                    <Icon className="w-5 h-5 text-mit-primary" />
                  </div>
                  <div>
                    <h3 className="text-card-title mb-1">{point.title}</h3>
                    <p className="text-card-desc">{point.description}</p>
                  </div>
                </motion.div>
              );
            })}

            {/* Mascot Bubble */}
            <motion.div
              variants={itemVariants}
              className="flex items-center gap-3 mt-6"
            >
              <img
                src="/agent.png"
                alt="부덕이"
                className="w-10 h-10 rounded-full"
              />
              <div className="glass-card px-4 py-2.5 rounded-2xl rounded-bl-sm">
                <p className="text-sm text-white/70">
                  {PROBLEM.mascotBubble}
                </p>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
