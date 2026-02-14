'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/stores/authStore';
import { usersAPI, tripsAPI } from '@/lib/api';
import { motion } from 'framer-motion';
import {
    Plus, MapPin, Calendar, DollarSign, Sparkles, ArrowRight,
    Globe, TrendingUp, Clock, User as UserIcon
} from 'lucide-react';
import { CardSkeleton } from '@/components/LoadingSkeleton';
import type { Trip, User, UserPreferences } from '@/types';
import styles from './page.module.css';

export default function DashboardPage() {
    const { userId } = useAuthStore();
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [trips, setTrips] = useState<Trip[]>([]);
    const [preferences, setPreferences] = useState<UserPreferences | null>(null);
    const [loading, setLoading] = useState(true);

    const loadData = useCallback(async () => {
        if (!userId) return;
        try {
            // Fetch user profile from API
            const userData = await usersAPI.getMe();
            setCurrentUser(userData);
        } catch {
            // fallback — user not available
        }

        try {
            const prefs = await usersAPI.getPreferences();
            setPreferences(prefs);
        } catch {
            // preferences not set yet
        }

        try {
            // Fetch real trips from the API
            const tripsData = await tripsAPI.getUserTrips(userId);
            setTrips(tripsData.trips);
        } catch {
            // no trips yet
            setTrips([]);
        }

        setLoading(false);
    }, [userId]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const greeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 17) return 'Good afternoon';
        return 'Good evening';
    };

    const userName = currentUser?.name?.split(' ')[0] || 'Traveler';

    return (
        <div className={styles.container}>
            {/* Header Section */}
            <div className={styles.header}>
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                >
                    <h1 className={styles.greeting}>
                        {greeting()}, <span className="gradient-text">{userName}</span>
                    </h1>
                    <p className={styles.subtitle}>
                        {trips.length > 0
                            ? `You have ${trips.length} trip${trips.length > 1 ? 's' : ''} planned. Ready for the next adventure?`
                            : 'Start planning your dream trip with our AI travel agent.'}
                    </p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.1 }}
                    className={styles.headerRight}
                >
                    {currentUser && (
                        <div className={styles.profileChip}>
                            <div className={styles.profileAvatar}>
                                <UserIcon size={16} />
                            </div>
                            <div className={styles.profileInfo}>
                                <span className={styles.profileName}>{currentUser.name}</span>
                                <span className={styles.profileEmail}>{currentUser.email}</span>
                            </div>
                        </div>
                    )}
                    <Link href="/chat" className={`btn btn-primary btn-lg ${styles.ctaButton}`}>
                        <Plus size={20} />
                        Plan a New Trip
                    </Link>
                </motion.div>
            </div>

            {/* Stats Cards */}
            <motion.div
                className={styles.statsGrid}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
            >
                <div className={styles.statCard}>
                    <div className={styles.statIcon}><Globe size={20} /></div>
                    <div>
                        <div className={styles.statValue}>{currentUser?.metadata?.total_trips || trips.length}</div>
                        <div className={styles.statLabel}>Trips Planned</div>
                    </div>
                </div>
                <div className={styles.statCard}>
                    <div className={styles.statIcon}><TrendingUp size={20} /></div>
                    <div>
                        <div className={styles.statValue}>{preferences?.travel_style?.length || 0}</div>
                        <div className={styles.statLabel}>Travel Styles</div>
                    </div>
                </div>
                <div className={styles.statCard}>
                    <div className={styles.statIcon}><Clock size={20} /></div>
                    <div>
                        <div className={styles.statValue}>
                            {currentUser?.metadata?.last_login
                                ? new Date(currentUser.metadata.last_login).toLocaleDateString()
                                : 'Today'}
                        </div>
                        <div className={styles.statLabel}>Last Active</div>
                    </div>
                </div>
            </motion.div>

            {/* Trips Section */}
            <div className={styles.section}>
                <div className={styles.sectionHeader}>
                    <h2>Your Trips</h2>
                    {trips.length > 0 && (
                        <Link href="/chat" className="btn btn-ghost btn-sm">
                            <Plus size={16} /> New Trip
                        </Link>
                    )}
                </div>

                {loading ? (
                    <div className={styles.tripsGrid}>
                        {[1, 2, 3].map((i) => <CardSkeleton key={i} />)}
                    </div>
                ) : trips.length === 0 ? (
                    <motion.div
                        className={styles.emptyState}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.2 }}
                    >
                        <div className={styles.emptyIcon}>
                            <Sparkles size={40} />
                        </div>
                        <h3>No trips yet</h3>
                        <p>Start a conversation with our AI travel agent to plan your first trip.</p>
                        <Link href="/chat" className="btn btn-primary">
                            <Sparkles size={18} />
                            Start Planning
                            <ArrowRight size={18} />
                        </Link>
                    </motion.div>
                ) : (
                    <div className={styles.tripsGrid}>
                        {trips.map((trip, i) => (
                            <motion.div
                                key={trip._id}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.05 }}
                            >
                                <Link href={`/itinerary/${trip._id}`} className={styles.tripCard}>
                                    <div className={styles.tripCardHeader}>
                                        <div className={`${styles.tripStatus} ${styles[`status_${trip.status}`]}`}>{trip.status}</div>
                                    </div>
                                    <h3 className={styles.tripTitle}>{trip.title}</h3>
                                    <div className={styles.tripMeta}>
                                        <span><MapPin size={14} /> {trip.trip_constraints.destination}</span>
                                        <span><Calendar size={14} /> {trip.trip_constraints.duration_days} days</span>
                                        <span><DollarSign size={14} /> ${trip.trip_constraints.budget}</span>
                                    </div>
                                    <div className={styles.tripDate}>
                                        {new Date(trip.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                                    </div>
                                </Link>
                            </motion.div>
                        ))}
                    </div>
                )}
            </div>

            {/* Quick Actions */}
            {preferences && (
                <motion.div
                    className={styles.section}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.25 }}
                >
                    <h2 className={styles.sectionHeader}>Quick Suggestions</h2>
                    <div className={styles.suggestionsGrid}>
                        {(preferences.preferred_destinations || []).slice(0, 3).map((dest, i) => (
                            <Link
                                key={i}
                                href={`/chat?destination=${encodeURIComponent(dest)}`}
                                className={styles.suggestionCard}
                            >
                                <MapPin size={16} />
                                <span>Plan a trip to {dest}</span>
                                <ArrowRight size={14} />
                            </Link>
                        ))}
                    </div>
                </motion.div>
            )}
        </div>
    );
}
