import { useEffect } from 'react';
import { IntroduceNav } from './introduce/IntroduceNav';
import { HeroSection } from './introduce/HeroSection';
import { ProblemSection } from './introduce/ProblemSection';
import { FeaturesSection } from './introduce/FeaturesSection';
import { DemoSection } from './introduce/DemoSection';
import { DifferentiationSection } from './introduce/DifferentiationSection';
import { TeamSection } from './introduce/TeamSection';
import { CTASection } from './introduce/CTASection';
import { CommitTimeline } from './introduce/CommitTimeline';

export function IntroducePage() {
  useEffect(() => {
    document.title = 'Mit — 회의의 진실을 관리하세요';
    return () => {
      document.title = 'Mit';
    };
  }, []);

  return (
    <div className="gradient-bg min-h-screen text-white overflow-x-hidden">
      <IntroduceNav />
      <CommitTimeline />
      <main>
        <HeroSection />
        <ProblemSection />
        <FeaturesSection />
        <DemoSection />
        <DifferentiationSection />
        <TeamSection />
        <CTASection />
      </main>
    </div>
  );
}
