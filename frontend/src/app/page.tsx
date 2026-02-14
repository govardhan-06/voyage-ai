'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Compass, Sparkles, Map, Shield, ArrowRight } from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';
import styles from './page.module.css';

export default function LandingPage() {
  const { isAuthenticated, isLoading } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <Link href="/" className={styles.logo}>
            <Compass size={28} />
            <span>Voyage<span className="gradient-text">AI</span></span>
          </Link>
          <div className={styles.headerActions}>
            <ThemeToggle />
            <Link href="/login" className="btn btn-ghost">Log In</Link>
            <Link href="/signup" className="btn btn-primary">Get Started</Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className={styles.hero}>
        <motion.div
          className={styles.heroContent}
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className={styles.heroBadge}>
            <Sparkles size={14} />
            <span>AI-Powered Travel Planning</span>
          </div>
          <h1 className={styles.heroTitle}>
            Your Dream Trip,<br />
            <span className="gradient-text">Planned by AI</span>
          </h1>
          <p className={styles.heroSubtext}>
            Tell our AI agent where you want to go. Get a personalized, day-by-day
            itinerary with real flights, hotels, and activities — in seconds.
          </p>
          <div className={styles.heroCta}>
            <Link href="/signup" className="btn btn-primary btn-lg">
              Start Planning <ArrowRight size={18} />
            </Link>
            <Link href="/login" className="btn btn-secondary btn-lg">
              I have an account
            </Link>
          </div>
        </motion.div>

        {/* Floating Cards */}
        <motion.div
          className={styles.heroVisual}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.2 }}
        >
          <div className={styles.floatingCard} style={{ top: '10%', left: '5%' }}>
            <div className={styles.floatingCardIcon}>🗼</div>
            <div>
              <div className={styles.floatingCardTitle}>Tokyo, Japan</div>
              <div className={styles.floatingCardSub}>5 days · $2,500</div>
            </div>
          </div>
          <div className={styles.floatingCard} style={{ top: '35%', right: '0%' }}>
            <div className={styles.floatingCardIcon}>🏖️</div>
            <div>
              <div className={styles.floatingCardTitle}>Bali, Indonesia</div>
              <div className={styles.floatingCardSub}>7 days · $1,800</div>
            </div>
          </div>
          <div className={styles.floatingCard} style={{ bottom: '10%', left: '15%' }}>
            <div className={styles.floatingCardIcon}>🏰</div>
            <div>
              <div className={styles.floatingCardTitle}>Paris, France</div>
              <div className={styles.floatingCardSub}>4 days · $3,200</div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Features */}
      <section className={styles.features}>
        <motion.div
          className={styles.featuresGrid}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, staggerChildren: 0.1 }}
        >
          {[
            { icon: <Sparkles size={24} />, title: 'AI-Powered', desc: 'Our AI agent understands your preferences and creates tailored itineraries.' },
            { icon: <Map size={24} />, title: 'Real Bookings', desc: 'Get actual flight and hotel recommendations with live pricing data.' },
            { icon: <Shield size={24} />, title: 'Full Control', desc: 'Review, modify, and approve every detail before finalizing your trip.' },
          ].map((f, i) => (
            <motion.div
              key={i}
              className={styles.featureCard}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <div className={styles.featureIcon}>{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <p>© 2026 VoyageAI</p>
      </footer>
    </div>
  );
}
