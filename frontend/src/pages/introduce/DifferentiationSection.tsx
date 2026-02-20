import { motion } from 'framer-motion';
import { Check, X } from 'lucide-react';
import { DIFFERENTIATION } from './constants';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12 } },
};

const rowVariants = {
  hidden: { opacity: 0, x: -30 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.5 } },
};

export function DifferentiationSection() {
  return (
    <section id="differentiation" className="py-24 sm:py-32 px-6">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <p className="text-section-header mb-3">COMPARISON</p>
          <h2 className="text-3xl sm:text-4xl font-bold text-white">
            {DIFFERENTIATION.headline}
          </h2>
        </motion.div>

        {/* Header Row */}
        <div className="hidden sm:grid grid-cols-3 gap-4 mb-4 px-4">
          <div />
          <p className="text-xs font-semibold text-white/40 uppercase tracking-wider text-center">
            일반 화상 회의
          </p>
          <p className="text-xs font-semibold text-mit-primary uppercase tracking-wider text-center">
            Mit
          </p>
        </div>

        {/* Rows */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          className="space-y-3"
        >
          {DIFFERENTIATION.rows.map((row, i) => (
            <motion.div
              key={i}
              variants={rowVariants}
              className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 glass-card p-4 rounded-xl"
            >
              <div className="flex items-center">
                <p className="text-sm font-semibold text-white/80">
                  {row.category}
                </p>
              </div>
              <div className="flex items-center gap-2 sm:justify-center">
                <X className="w-4 h-4 text-red-400/60 flex-shrink-0 hidden sm:block" />
                <p className="text-sm text-white/40">{row.general}</p>
              </div>
              <div className="flex items-center gap-2 sm:justify-center">
                <Check className="w-4 h-4 text-mit-success flex-shrink-0 hidden sm:block" />
                <p className="text-sm text-mit-primary font-medium">
                  {row.mit}
                </p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
