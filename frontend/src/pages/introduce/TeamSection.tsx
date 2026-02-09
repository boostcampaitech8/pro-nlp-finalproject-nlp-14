import { motion } from 'framer-motion';
import { Users } from 'lucide-react';
import { TEAM } from './constants';

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const itemVariants = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.4 } },
};

function AvatarStack() {
  const colors = [
    'from-mit-primary to-blue-400',
    'from-mit-purple to-fuchsia-400',
    'from-emerald-500 to-teal-400',
    'from-amber-500 to-orange-400',
  ];

  return (
    <div className="flex items-center justify-center mb-8">
      <div className="flex -space-x-3">
        {colors.map((gradient, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1, duration: 0.4 }}
            className={`w-12 h-12 rounded-full bg-gradient-to-br ${gradient} border-2 border-[#0f172a] flex items-center justify-center`}
          >
            <Users className="w-5 h-5 text-white/80" />
          </motion.div>
        ))}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.4, type: 'spring' }}
          className="w-12 h-12 rounded-full bg-white/10 border-2 border-dashed border-white/20 flex items-center justify-center"
        >
          <span className="text-white/50 text-lg font-light">+</span>
        </motion.div>
      </div>
    </div>
  );
}

export function TeamSection() {
  return (
    <section id="team" className="py-24 sm:py-32 px-6">
      <div className="max-w-3xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.5 }}
        >
          <p className="text-section-header mb-3">TEAM</p>
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            {TEAM.headline}
          </h2>
          <p className="text-lg text-white/60 mb-12">{TEAM.subtext}</p>
        </motion.div>

        <AvatarStack />

        {/* Feature Pills */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="flex flex-wrap justify-center gap-3"
        >
          {TEAM.features.map((feature, i) => (
            <motion.span
              key={i}
              variants={itemVariants}
              className="glass-card px-4 py-2 rounded-full text-sm text-white/70 border border-white/[0.08] hover:border-mit-primary/30 hover:text-white/90 transition-all duration-200"
            >
              {feature.label}
            </motion.span>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
