import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { SECTION_IDS } from './constants';

export function CommitTimeline() {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.id;
            const idx = SECTION_IDS.indexOf(id as (typeof SECTION_IDS)[number]);
            if (idx !== -1) setActiveIndex(idx);
          }
        });
      },
      { threshold: 0.3 },
    );

    SECTION_IDS.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <div className="fixed left-8 top-1/2 -translate-y-1/2 z-40 hidden lg:flex flex-col items-center gap-0">
      {/* Vertical Line */}
      <div className="absolute inset-0 flex justify-center">
        <div className="w-[1px] h-full bg-white/[0.06]" />
      </div>

      {SECTION_IDS.map((_, i) => {
        const isActive = i <= activeIndex;
        return (
          <div key={i} className="relative py-6">
            <motion.div
              className={`w-3 h-3 rounded-full border-2 transition-colors duration-300 ${
                isActive
                  ? 'bg-mit-primary border-mit-primary/60'
                  : 'bg-transparent border-white/20'
              }`}
              animate={
                i === activeIndex
                  ? { scale: [1, 1.4, 1] }
                  : { scale: 1 }
              }
              transition={{
                duration: 1.2,
                repeat: i === activeIndex ? Infinity : 0,
                ease: 'easeInOut',
              }}
            />
          </div>
        );
      })}
    </div>
  );
}
