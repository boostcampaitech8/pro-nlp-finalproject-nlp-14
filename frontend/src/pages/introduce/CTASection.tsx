import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Button } from '@/app/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { CTA } from './constants';

export function CTASection() {
  const { isAuthenticated } = useAuth();

  return (
    <section
      id="cta"
      className="relative min-h-screen flex flex-col items-center justify-center px-6"
    >
      {/* Background Glow */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-[500px] h-[500px] bg-mit-purple/10 rounded-full blur-[150px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.6 }}
        className="relative z-10 text-center"
      >
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-10">
          {CTA.headline}
        </h2>

        {/* Primary CTA */}
        <Link to={isAuthenticated ? '/' : '/login'}>
          <Button className="bg-gradient-to-r from-mit-primary to-mit-purple hover:from-mit-primary/90 hover:to-mit-purple/90 text-white px-10 h-14 text-lg font-semibold rounded-xl shadow-[0_4px_24px_rgba(99,102,241,0.4)] animate-[nudge-glow_2s_ease-in-out_infinite]">
            {isAuthenticated ? 'Spotlight으로 이동' : CTA.ctaPrimary}
          </Button>
        </Link>

        {/* Login Link - 비인증 사용자만 표시 */}
        {!isAuthenticated && (
          <p className="mt-6 text-sm text-white/40">
            {CTA.loginText}{' '}
            <Link
              to="/login"
              className="text-mit-primary hover:text-mit-primary/80 transition-colors underline underline-offset-4"
            >
              {CTA.loginLink}
            </Link>
          </p>
        )}
      </motion.div>
    </section>
  );
}
