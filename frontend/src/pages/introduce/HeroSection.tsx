import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Layers, ChevronDown } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/app/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { HERO } from './constants';

function TypewriterDemo() {
  const [displayText, setDisplayText] = useState('');
  const [showResponse, setShowResponse] = useState(false);
  const fullText = HERO.typewriterText;

  useEffect(() => {
    let index = 0;
    const interval = setInterval(() => {
      if (index <= fullText.length) {
        setDisplayText(fullText.slice(0, index));
        index++;
      } else {
        clearInterval(interval);
        setTimeout(() => setShowResponse(true), 400);
      }
    }, 60);
    return () => clearInterval(interval);
  }, [fullText]);

  return (
    <div className="w-full max-w-xl mx-auto mt-12">
      {/* Faux Spotlight Input */}
      <div className="glass-input px-5 py-3.5 flex items-center gap-3">
        <span className="text-white/30 text-sm">{'>'}</span>
        <span className="text-white/90 text-sm">
          {displayText}
          <span className="inline-block w-[2px] h-4 bg-mit-primary ml-0.5 animate-[typewriter-cursor_0.8s_ease-in-out_infinite]" />
        </span>
      </div>

      {/* AI Response Bubble */}
      {showResponse && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mt-4 glass-card p-4 flex items-start gap-3"
        >
          <img
            src="/agent.png"
            alt="부덕이"
            className="w-8 h-8 rounded-full flex-shrink-0"
          />
          <div>
            <p className="text-xs text-mit-purple font-semibold mb-1">
              부덕이
            </p>
            <p className="text-sm text-white/70 leading-relaxed">
              {HERO.aiResponse}
            </p>
          </div>
        </motion.div>
      )}
    </div>
  );
}

export function HeroSection() {
  const { isAuthenticated } = useAuth();

  const handleScrollDown = () => {
    document.getElementById('problem')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section
      id="hero"
      className="relative min-h-screen flex flex-col items-center justify-center px-6 pt-20 overflow-hidden"
    >
      {/* Background Orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-mit-primary/10 rounded-full blur-[120px] animate-[orbit_20s_linear_infinite]" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-mit-purple/10 rounded-full blur-[100px] animate-[orbit_25s_linear_infinite_reverse]" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 text-center max-w-3xl"
      >
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="icon-container w-12 h-12 rounded-xl">
            <Layers className="w-6 h-6 text-white" />
          </div>
          <div className="text-left">
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Mit
            </h2>
            <p className="text-xs text-white/40">Meeting Intelligence</p>
          </div>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white leading-tight mb-6">
          {HERO.headline}
        </h1>
        <p className="text-lg text-white/60 leading-relaxed max-w-2xl mx-auto mb-10">
          {HERO.subtext}
        </p>

        {/* Mascot */}
        <div className="flex justify-center mb-10">
          <div className="relative">
            <img
              src="/agent.png"
              alt="부덕이 마스코트"
              className="w-24 h-24 rounded-2xl animate-float"
            />
            <div className="absolute inset-0 rounded-2xl shadow-[0_0_40px_rgba(139,92,246,0.3)]" />
          </div>
        </div>

        {/* CTA Buttons */}
        <div className="flex items-center justify-center gap-4">
          <Link to={isAuthenticated ? '/' : '/login'}>
            <Button className="bg-gradient-to-r from-mit-primary to-mit-purple hover:from-mit-primary/90 hover:to-mit-purple/90 text-white px-8 h-12 text-base font-semibold rounded-xl shadow-[0_4px_20px_rgba(99,102,241,0.3)]">
              {isAuthenticated ? 'Spotlight으로 이동' : HERO.ctaPrimary}
            </Button>
          </Link>
          <Button variant="glass" className="h-12 px-6 text-base rounded-xl" onClick={handleScrollDown}>
            {HERO.ctaSecondary}
          </Button>
        </div>

        {/* Typewriter Demo */}
        <TypewriterDemo />
      </motion.div>

      {/* Scroll Indicator */}
      <motion.button
        onClick={handleScrollDown}
        className="absolute bottom-8 text-white/30 hover:text-white/60 transition-colors"
        animate={{ y: [0, 8, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
      >
        <ChevronDown className="w-6 h-6" />
      </motion.button>
    </section>
  );
}
