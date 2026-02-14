'use client';

import { useState, useRef, useEffect, FormEvent, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { tripsAPI } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Send, Sparkles, Bot, User, Loader2, Check, X, Edit3,
    MapPin, Clock, DollarSign, Calendar, ArrowRight, Plane
} from 'lucide-react';
import type { ChatMessage, ChatResponse, Itinerary, ItineraryVersion } from '@/types';
import styles from './page.module.css';

export default function ChatPage() {
    const { userId } = useAuthStore();
    const router = useRouter();
    const searchParams = useSearchParams();

    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [threadId, setThreadId] = useState<string | null>(null);
    const [sending, setSending] = useState(false);
    const [currentStatus, setCurrentStatus] = useState<string | null>(null);
    const [reviewItinerary, setReviewItinerary] = useState<Itinerary | null>(null);
    const [completedTripId, setCompletedTripId] = useState<string | null>(null);
    const [finalItinerary, setFinalItinerary] = useState<ItineraryVersion | null>(null);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Auto-fill destination from URL params
    useEffect(() => {
        const dest = searchParams.get('destination');
        if (dest) {
            setInput(`Plan a trip to ${dest}`);
        }
    }, [searchParams]);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, reviewItinerary, finalItinerary, scrollToBottom]);

    // Auto-fetch itinerary on completion
    const fetchFinalItinerary = useCallback(async (tripId: string) => {
        try {
            const itinerary = await tripsAPI.getItinerary(tripId);
            setFinalItinerary(itinerary);
        } catch {
            // itinerary might not be available yet
        }
    }, []);

    const sendMessage = async (messageText?: string) => {
        const text = messageText || input.trim();
        if (!text || !userId || sending) return;

        const userMessage: ChatMessage = {
            role: 'user',
            content: text,
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setSending(true);
        setReviewItinerary(null);

        try {
            const response: ChatResponse = await tripsAPI.chat({
                user_id: userId,
                message: text,
                thread_id: threadId,
            });

            setThreadId(response.thread_id);
            setCurrentStatus(response.status);

            const aiMessage: ChatMessage = {
                role: 'ai',
                content: response.message,
                timestamp: new Date().toISOString(),
                data: response.data,
                status: response.status,
            };

            setMessages((prev) => [...prev, aiMessage]);

            // Handle statuses
            if (response.status === 'reviewing' && response.data?.itinerary) {
                setReviewItinerary(response.data.itinerary);
            }

            if (response.status === 'complete' && response.data?.trip_id) {
                setCompletedTripId(response.data.trip_id);
                // Auto-fetch the finalized itinerary
                fetchFinalItinerary(response.data.trip_id);
            }
        } catch {
            const errorMsg: ChatMessage = {
                role: 'ai',
                content: 'Sorry, something went wrong. Please try again.',
                timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, errorMsg]);
        } finally {
            setSending(false);
            inputRef.current?.focus();
        }
    };

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        sendMessage();
    };

    const handleApprove = () => {
        sendMessage('approve');
    };

    const handleRevise = (feedback: string) => {
        sendMessage(feedback);
    };

    return (
        <div className={styles.container}>
            {/* Chat Header */}
            <div className={styles.chatHeader}>
                <div className={styles.headerInfo}>
                    <div className={styles.agentAvatar}>
                        <Bot size={20} />
                    </div>
                    <div>
                        <h2 className={styles.headerTitle}>AI Travel Agent</h2>
                        <div className={styles.headerStatus}>
                            {sending ? (
                                <><Loader2 size={12} className={styles.spinIcon} /> Planning...</>
                            ) : currentStatus ? (
                                <><span className={styles.statusDot} /> {currentStatus === 'clarifying' ? 'Gathering details' : currentStatus === 'reviewing' ? 'Awaiting review' : currentStatus === 'complete' ? 'Trip finalized' : 'Processing'}</>
                            ) : (
                                <><span className={styles.statusDot} /> Ready to help</>
                            )}
                        </div>
                    </div>
                </div>
                {completedTripId && (
                    <button
                        className="btn btn-primary btn-sm"
                        onClick={() => router.push(`/itinerary/${completedTripId}`)}
                    >
                        View Full Itinerary <ArrowRight size={14} />
                    </button>
                )}
            </div>

            {/* Messages Area — single column */}
            <div className={styles.messagesArea}>
                {messages.length === 0 && (
                    <div className={styles.welcomeMessage}>
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className={styles.welcomeContent}
                        >
                            <div className={styles.welcomeIcon}>
                                <Plane size={32} />
                            </div>
                            <h3>Where would you like to go?</h3>
                            <p>Tell me about your dream trip and I&apos;ll create a personalized itinerary for you.</p>
                            <div className={styles.quickPrompts}>
                                {[
                                    'Plan a 5-day trip to Tokyo, Japan',
                                    'Weekend getaway in Paris',
                                    'Adventure trip to Bali for a week',
                                ].map((prompt, i) => (
                                    <button
                                        key={i}
                                        className={styles.quickPrompt}
                                        onClick={() => {
                                            setInput(prompt);
                                            sendMessage(prompt);
                                        }}
                                    >
                                        <Sparkles size={14} />
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        </motion.div>
                    </div>
                )}

                <div className={styles.messagesList}>
                    <AnimatePresence>
                        {messages.map((msg, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className={`${styles.messageBubble} ${msg.role === 'user' ? styles.userBubble : styles.aiBubble}`}
                            >
                                <div className={styles.messageAvatar}>
                                    {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                                </div>
                                <div className={styles.messageContent}>
                                    <div className={styles.messageText}>{msg.content}</div>

                                    {/* Slots collected indicator */}
                                    {msg.data?.slots_collected && (
                                        <div className={styles.slotsIndicator}>
                                            {(Object.entries(msg.data.slots_collected) as [string, string | number | boolean | null | undefined][])
                                                .filter(([, val]) => val != null)
                                                .map(([key, val]) => (
                                                    <span key={key} className={styles.slotChip}>
                                                        <Check size={12} /> {key.replace(/_/g, ' ')}: {String(val)}
                                                    </span>
                                                ))}
                                        </div>
                                    )}

                                    {/* Status badge */}
                                    {msg.status && (
                                        <div className={`${styles.statusBadge} ${styles[`status_${msg.status}`]}`}>
                                            {msg.status === 'reviewing' ? '📋 Review Itinerary Below' :
                                                msg.status === 'complete' ? '✅ Trip Finalized!' :
                                                    msg.status === 'clarifying' ? '💭 More details needed' :
                                                        '⏳ Processing'}
                                        </div>
                                    )}

                                    <div className={styles.messageTime}>
                                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>

                    {/* Typing indicator */}
                    {sending && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className={`${styles.messageBubble} ${styles.aiBubble}`}
                        >
                            <div className={styles.messageAvatar}><Bot size={16} /></div>
                            <div className={styles.typingIndicator}>
                                <span /><span /><span />
                            </div>
                        </motion.div>
                    )}

                    {/* Inline Itinerary Preview (while reviewing) */}
                    <AnimatePresence>
                        {reviewItinerary && (
                            <motion.div
                                className={styles.itineraryInline}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 20 }}
                            >
                                <div className={styles.itineraryInlineHeader}>
                                    <h3>📋 Draft Itinerary</h3>
                                    <div className={styles.itineraryCost}>
                                        <DollarSign size={16} />
                                        {reviewItinerary.total_cost_estimate} {reviewItinerary.currency}
                                    </div>
                                </div>

                                {reviewItinerary.summary && (
                                    <p className={styles.itinerarySummary}>{reviewItinerary.summary}</p>
                                )}

                                <div className={styles.itineraryDays}>
                                    {reviewItinerary.days.map((day) => (
                                        <div key={day.day_number} className={styles.dayCard}>
                                            <div className={styles.dayHeader}>
                                                <Calendar size={14} />
                                                <span>Day {day.day_number}</span>
                                                {day.date && <span className={styles.dayDate}>{day.date}</span>}
                                            </div>
                                            <div className={styles.activities}>
                                                {day.activities.map((act, j) => (
                                                    <div key={j} className={styles.activityItem}>
                                                        <div className={styles.activityTime}>
                                                            <Clock size={12} /> {act.time}
                                                        </div>
                                                        <div className={styles.activityInfo}>
                                                            <div className={styles.activityTitle}>{act.title}</div>
                                                            <div className={styles.activityLocation}>
                                                                <MapPin size={12} /> {act.location?.name || act.location_name}
                                                            </div>
                                                            {act.cost_estimate > 0 && (
                                                                <div className={styles.activityCost}>
                                                                    ${act.cost_estimate}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className={styles.reviewActions}>
                                    <button className="btn btn-primary" onClick={handleApprove}>
                                        <Check size={18} /> Approve & Save
                                    </button>
                                    <button
                                        className="btn btn-secondary"
                                        onClick={() => {
                                            const feedback = prompt('What would you like to change?');
                                            if (feedback) handleRevise(feedback);
                                        }}
                                    >
                                        <Edit3 size={18} /> Request Changes
                                    </button>
                                    <button
                                        className="btn btn-ghost"
                                        onClick={() => setReviewItinerary(null)}
                                    >
                                        <X size={18} /> Dismiss
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Inline Final Itinerary (after completion) */}
                    <AnimatePresence>
                        {finalItinerary && (
                            <motion.div
                                className={styles.itineraryInline}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 20 }}
                            >
                                <div className={styles.itineraryInlineHeader}>
                                    <h3>✅ Final Itinerary</h3>
                                    <div className={styles.itineraryCost}>
                                        <DollarSign size={16} />
                                        {finalItinerary.itinerary.total_cost_estimate} {finalItinerary.itinerary.currency}
                                    </div>
                                </div>

                                {finalItinerary.change_summary && (
                                    <p className={styles.itinerarySummary}>{finalItinerary.change_summary}</p>
                                )}

                                <div className={styles.itineraryDays}>
                                    {finalItinerary.itinerary.days.map((day) => (
                                        <div key={day.day_number} className={styles.dayCard}>
                                            <div className={styles.dayHeader}>
                                                <Calendar size={14} />
                                                <span>Day {day.day_number}</span>
                                                {day.date && <span className={styles.dayDate}>{day.date}</span>}
                                            </div>
                                            <div className={styles.activities}>
                                                {day.activities.map((act, j) => (
                                                    <div key={j} className={styles.activityItem}>
                                                        <div className={styles.activityTime}>
                                                            <Clock size={12} /> {act.time}
                                                        </div>
                                                        <div className={styles.activityInfo}>
                                                            <div className={styles.activityTitle}>{act.title}</div>
                                                            <div className={styles.activityLocation}>
                                                                <MapPin size={12} /> {act.location?.name || act.location_name}
                                                            </div>
                                                            {act.cost_estimate > 0 && (
                                                                <div className={styles.activityCost}>
                                                                    ${act.cost_estimate}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {completedTripId && (
                                    <div className={styles.reviewActions}>
                                        <button
                                            className="btn btn-primary"
                                            onClick={() => router.push(`/itinerary/${completedTripId}`)}
                                        >
                                            View Full Itinerary <ArrowRight size={18} />
                                        </button>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Input Area */}
            <form onSubmit={handleSubmit} className={styles.inputArea}>
                <div className={styles.inputWrapper}>
                    <input
                        ref={inputRef}
                        type="text"
                        className={styles.chatInput}
                        placeholder={
                            currentStatus === 'complete'
                                ? 'Trip complete! View your itinerary above.'
                                : currentStatus === 'reviewing'
                                    ? 'Describe any changes, or approve the itinerary...'
                                    : 'Tell me about your dream trip...'
                        }
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={sending || currentStatus === 'complete'}
                    />
                    <button
                        type="submit"
                        className={styles.sendButton}
                        disabled={!input.trim() || sending || currentStatus === 'complete'}
                    >
                        {sending ? <Loader2 size={20} className={styles.spinIcon} /> : <Send size={20} />}
                    </button>
                </div>
            </form>
        </div>
    );
}
