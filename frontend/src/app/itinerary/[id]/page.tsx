'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { tripsAPI } from '@/lib/api';
import { motion } from 'framer-motion';
import {
    MapPin, Clock, DollarSign, Calendar, Tag, ArrowLeft,
    Edit3, Check, X, ExternalLink, Loader2
} from 'lucide-react';
import { ItinerarySkeleton } from '@/components/LoadingSkeleton';
import type { Trip, ItineraryVersion, Activity } from '@/types';
import styles from './page.module.css';

export default function ItineraryPage() {
    const params = useParams();
    const router = useRouter();
    const tripId = params.id as string;

    const [trip, setTrip] = useState<Trip | null>(null);
    const [itineraryVersion, setItineraryVersion] = useState<ItineraryVersion | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [editingActivity, setEditingActivity] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState('');
    const [editDesc, setEditDesc] = useState('');

    const loadData = useCallback(async () => {
        try {
            const [tripData, itinData] = await Promise.all([
                tripsAPI.getTrip(tripId),
                tripsAPI.getItinerary(tripId),
            ]);
            setTrip(tripData);
            setItineraryVersion(itinData);
        } catch {
            setError('Failed to load itinerary. It might not exist yet.');
        } finally {
            setLoading(false);
        }
    }, [tripId]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const itinerary = itineraryVersion?.itinerary;

    const startEdit = (dayNum: number, actIdx: number, activity: Activity) => {
        setEditingActivity(`${dayNum}-${actIdx}`);
        setEditTitle(activity.title);
        setEditDesc(activity.description);
    };

    const saveEdit = (dayNum: number, actIdx: number) => {
        if (!itineraryVersion) return;
        const updated = { ...itineraryVersion };
        const day = updated.itinerary.days.find((d) => d.day_number === dayNum);
        if (day) {
            day.activities[actIdx] = {
                ...day.activities[actIdx],
                title: editTitle,
                description: editDesc,
            };
        }
        setItineraryVersion(updated);
        setEditingActivity(null);
    };

    const totalCost = itinerary?.days.reduce((sum, day) =>
        sum + day.activities.reduce((a, act) => a + (act.cost_estimate || 0), 0), 0) || 0;

    if (loading) {
        return (
            <div className={styles.container}>
                <ItinerarySkeleton />
            </div>
        );
    }

    if (error || !itinerary) {
        return (
            <div className={styles.container}>
                <div className={styles.errorState}>
                    <h2>Itinerary Not Found</h2>
                    <p>{error || 'This itinerary does not exist.'}</p>
                    <button className="btn btn-primary" onClick={() => router.push('/dashboard')}>
                        <ArrowLeft size={18} /> Back to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className={styles.container}>
            {/* Header */}
            <motion.div
                className={styles.header}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <button className="btn btn-ghost btn-sm" onClick={() => router.push('/dashboard')}>
                    <ArrowLeft size={16} /> Back
                </button>

                <div className={styles.headerContent}>
                    <h1 className={styles.title}>{trip?.title || itinerary.title || 'Your Itinerary'}</h1>
                    {itinerary.summary && (
                        <p className={styles.summary}>{itinerary.summary}</p>
                    )}
                    <div className={styles.headerMeta}>
                        {trip?.trip_constraints && (
                            <>
                                <span className={styles.metaItem}>
                                    <MapPin size={16} /> {trip.trip_constraints.destination}
                                </span>
                                <span className={styles.metaItem}>
                                    <Calendar size={16} /> {trip.trip_constraints.duration_days} days
                                </span>
                            </>
                        )}
                        <span className={styles.metaItem}>
                            <DollarSign size={16} />
                            {itinerary.total_cost_estimate || totalCost} {itinerary.currency || 'USD'}
                        </span>
                    </div>
                </div>
            </motion.div>

            {/* Content */}
            <div className={styles.content}>
                {/* Timeline */}
                <div className={styles.timeline}>
                    {itinerary.days.map((day, dayIdx) => (
                        <motion.div
                            key={day.day_number}
                            className={styles.daySection}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: dayIdx * 0.08 }}
                        >
                            <div className={styles.dayHeader}>
                                <div className={styles.dayBadge}>Day {day.day_number}</div>
                                {day.date && (
                                    <span className={styles.dayDate}>
                                        {new Date(day.date).toLocaleDateString('en-US', {
                                            weekday: 'long',
                                            month: 'long',
                                            day: 'numeric',
                                        })}
                                    </span>
                                )}
                            </div>

                            <div className={styles.activitiesList}>
                                {day.activities.map((activity, actIdx) => {
                                    const isEditing = editingActivity === `${day.day_number}-${actIdx}`;
                                    const loc = activity.location || {
                                        name: activity.location_name,
                                        address: activity.location_address,
                                    };

                                    return (
                                        <div key={actIdx} className={styles.activityCard}>
                                            <div className={styles.timelineConnector}>
                                                <div className={styles.timelineDot} />
                                                {actIdx < day.activities.length - 1 && <div className={styles.timelineLine} />}
                                            </div>

                                            <div className={styles.activityContent}>
                                                <div className={styles.activityTime}>
                                                    <Clock size={14} /> {activity.time}
                                                </div>

                                                {isEditing ? (
                                                    <div className={styles.editForm}>
                                                        <input
                                                            type="text"
                                                            className="input"
                                                            value={editTitle}
                                                            onChange={(e) => setEditTitle(e.target.value)}
                                                            placeholder="Activity title"
                                                        />
                                                        <textarea
                                                            className={`input ${styles.editTextarea}`}
                                                            value={editDesc}
                                                            onChange={(e) => setEditDesc(e.target.value)}
                                                            placeholder="Description"
                                                            rows={3}
                                                        />
                                                        <div className={styles.editActions}>
                                                            <button className="btn btn-primary btn-sm" onClick={() => saveEdit(day.day_number, actIdx)}>
                                                                <Check size={14} /> Save
                                                            </button>
                                                            <button className="btn btn-ghost btn-sm" onClick={() => setEditingActivity(null)}>
                                                                <X size={14} /> Cancel
                                                            </button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <>
                                                        <div className={styles.activityHeader}>
                                                            <h4 className={styles.activityTitle}>{activity.title}</h4>
                                                            <button
                                                                className={`btn btn-ghost btn-icon ${styles.editBtn}`}
                                                                onClick={() => startEdit(day.day_number, actIdx, activity)}
                                                            >
                                                                <Edit3 size={14} />
                                                            </button>
                                                        </div>
                                                        <p className={styles.activityDesc}>{activity.description}</p>

                                                        <div className={styles.activityMeta}>
                                                            {loc?.name && (
                                                                <span className={styles.locationChip}>
                                                                    <MapPin size={12} /> {loc.name}
                                                                </span>
                                                            )}
                                                            {activity.cost_estimate > 0 && (
                                                                <span className={styles.costChip}>
                                                                    <DollarSign size={12} /> ${activity.cost_estimate}
                                                                </span>
                                                            )}
                                                            {loc?.name && (
                                                                <a
                                                                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(loc.name + ' ' + (loc.address || ''))}`}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className={styles.mapLink}
                                                                >
                                                                    <ExternalLink size={12} /> Maps
                                                                </a>
                                                            )}
                                                        </div>

                                                        {activity.tags && activity.tags.length > 0 && (
                                                            <div className={styles.tags}>
                                                                {activity.tags.map((tag) => (
                                                                    <span key={tag} className={styles.tag}>
                                                                        <Tag size={10} /> {tag}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </motion.div>
                    ))}
                </div>

                {/* Cost Summary Sidebar */}
                <div className={styles.sidebar}>
                    <div className={styles.costSummary}>
                        <h3>Cost Summary</h3>
                        <div className={styles.costBreakdown}>
                            {itinerary.days.map((day) => {
                                const dayCost = day.activities.reduce((s, a) => s + (a.cost_estimate || 0), 0);
                                return (
                                    <div key={day.day_number} className={styles.costRow}>
                                        <span>Day {day.day_number}</span>
                                        <span>${dayCost}</span>
                                    </div>
                                );
                            })}
                            <div className={`${styles.costRow} ${styles.costTotal}`}>
                                <span>Total</span>
                                <span>${totalCost}</span>
                            </div>
                        </div>
                    </div>

                    {trip?.trip_constraints && (
                        <div className={styles.tripDetails}>
                            <h3>Trip Details</h3>
                            <div className={styles.detailRow}>
                                <span>Destination</span>
                                <span>{trip.trip_constraints.destination}</span>
                            </div>
                            <div className={styles.detailRow}>
                                <span>Duration</span>
                                <span>{trip.trip_constraints.duration_days} days</span>
                            </div>
                            <div className={styles.detailRow}>
                                <span>Budget</span>
                                <span>${trip.trip_constraints.budget}</span>
                            </div>
                            <div className={styles.detailRow}>
                                <span>Travelers</span>
                                <span>{trip.trip_constraints.traveler_count} ({trip.trip_constraints.travel_group})</span>
                            </div>
                            {trip.trip_constraints.start_date && (
                                <div className={styles.detailRow}>
                                    <span>Start Date</span>
                                    <span>{new Date(trip.trip_constraints.start_date).toLocaleDateString()}</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
