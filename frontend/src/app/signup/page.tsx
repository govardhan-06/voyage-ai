'use client';

import { useState, FormEvent, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/stores/authStore';
import { motion } from 'framer-motion';
import { Compass, Mail, Lock, User, ArrowRight, AlertCircle } from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';
import styles from './page.module.css';

export default function SignupPage() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { register, isAuthenticated, isLoading } = useAuthStore();
    const router = useRouter();

    useEffect(() => {
        if (!isLoading && isAuthenticated) {
            router.push('/preferences');
        }
    }, [isAuthenticated, isLoading, router]);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError('');

        if (!name || !email || !password || !confirmPassword) {
            setError('Please fill in all fields.');
            return;
        }

        if (password.length < 6) {
            setError('Password must be at least 6 characters.');
            return;
        }

        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }

        setLoading(true);
        try {
            await register(name, email, password);
            router.push('/preferences');
        } catch (err: unknown) {
            const axiosErr = err as { response?: { data?: { detail?: string } } };
            setError(axiosErr.response?.data?.detail || 'Registration failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.container}>
            <div className={styles.themeTogglePos}>
                <ThemeToggle />
            </div>

            <motion.div
                className={styles.formWrapper}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <div className={styles.formHeader}>
                    <Link href="/" className={styles.logo}>
                        <Compass size={32} />
                        <span>Voyage<span className="gradient-text">AI</span></span>
                    </Link>
                    <h1 className={styles.title}>Create your account</h1>
                    <p className={styles.subtitle}>Start planning incredible trips with AI</p>
                </div>

                {error && (
                    <motion.div
                        className={styles.errorBanner}
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                    >
                        <AlertCircle size={16} />
                        <span>{error}</span>
                    </motion.div>
                )}

                <form onSubmit={handleSubmit} className={styles.form}>
                    <div className="input-group">
                        <label className="input-label">Full Name</label>
                        <div className={styles.inputIcon}>
                            <User size={18} className={styles.icon} />
                            <input
                                type="text"
                                className="input"
                                placeholder="John Doe"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                style={{ paddingLeft: 44 }}
                            />
                        </div>
                    </div>

                    <div className="input-group">
                        <label className="input-label">Email</label>
                        <div className={styles.inputIcon}>
                            <Mail size={18} className={styles.icon} />
                            <input
                                type="email"
                                className="input"
                                placeholder="you@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                style={{ paddingLeft: 44 }}
                            />
                        </div>
                    </div>

                    <div className="input-group">
                        <label className="input-label">Password</label>
                        <div className={styles.inputIcon}>
                            <Lock size={18} className={styles.icon} />
                            <input
                                type="password"
                                className="input"
                                placeholder="Min. 6 characters"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                style={{ paddingLeft: 44 }}
                            />
                        </div>
                    </div>

                    <div className="input-group">
                        <label className="input-label">Confirm Password</label>
                        <div className={styles.inputIcon}>
                            <Lock size={18} className={styles.icon} />
                            <input
                                type="password"
                                className="input"
                                placeholder="Re-enter password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                style={{ paddingLeft: 44 }}
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        className="btn btn-primary btn-lg"
                        disabled={loading}
                        style={{ width: '100%', marginTop: 8 }}
                    >
                        {loading ? (
                            <span className={styles.spinner} />
                        ) : (
                            <>Create Account <ArrowRight size={18} /></>
                        )}
                    </button>
                </form>

                <p className={styles.footerText}>
                    Already have an account?{' '}
                    <Link href="/login" className={styles.link}>Sign In</Link>
                </p>
            </motion.div>
        </div>
    );
}
