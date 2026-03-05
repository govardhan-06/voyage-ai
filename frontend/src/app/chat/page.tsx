'use client';

import { useState, useRef, useEffect, FormEvent, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { tripsAPI } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Send, Sparkles, Bot, User, Loader2, Check, X, Edit3,
    MapPin, Clock, IndianRupee, Calendar, ArrowRight, Plane,
    Hotel, ChevronRight
} from 'lucide-react';
import type { ChatMessage, ChatResponse, Itinerary, ItineraryVersion, FlightOption, HotelOption } from '@/types';
import { formatINR } from '@/lib/format';
import styles from './page.module.css';

// ── Flight Selection Card ──
function FlightCard({
    flight,
    onSelect,
}: {
    flight: FlightOption & { index: number };
    onSelect: (idx: number) => void;
}) {
    const depTime = flight.departure_time
        ? new Date(flight.departure_time).toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
        : 'TBD';
    const arrTime = flight.arrival_time
        ? new Date(flight.arrival_time).toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
        : 'TBD';
    const stopsText = flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop(s)`;

    return (
        <motion.button
            className={styles.selectionCard}
            onClick={() => onSelect(flight.index)}
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
        >
            <div className={styles.selectionCardNumber}>{flight.index}</div>
            <div className={styles.selectionCardBody}>
                <div className={styles.selectionCardTitle}>
                    <Plane size={14} />
                    <span>{flight.airline} {flight.flight_number}</span>
                    <span className={styles.selectionBadge}>{flight.booking_class || 'ECONOMY'}</span>
                    {stopsText !== 'Non-stop' && <span className={styles.stopsBadge}>{stopsText}</span>}
                </div>
                <div className={styles.flightTimes}>
                    <span>{depTime}</span>
                    <div className={styles.flightArrow}>
                        <div className={styles.flightLine} />
                        <ChevronRight size={12} />
                    </div>
                    <span>{arrTime}</span>
                    {flight.duration && <span className={styles.flightDuration}>{flight.duration}</span>}
                </div>
            </div>
            <div className={styles.selectionCardPrice}>
                {flight.price_inr > 0 ? formatINR(flight.price_inr) : 'Quote on request'}
            </div>
        </motion.button>
    );
}

// ── Hotel Selection Card ──
function HotelCard({
    hotel,
    onSelect,
}: {
    hotel: HotelOption & { index: number };
    onSelect: (idx: number) => void;
}) {
    const price = hotel.price_inr || hotel.best_price_inr || 0;
    const perNight = hotel.price_per_night_inr || hotel.best_price_per_night_inr || 0;

    return (
        <motion.button
            className={styles.selectionCard}
            onClick={() => onSelect(hotel.index!)}
            whileHover={{ scale: 1.02, y: -2 }}
            whileTap={{ scale: 0.98 }}
        >
            <div className={styles.selectionCardNumber}>{hotel.index}</div>
            <div className={styles.selectionCardBody}>
                <div className={styles.selectionCardTitle}>
                    <Hotel size={14} />
                    <span>{hotel.name}</span>
                </div>
                <div className={styles.hotelMeta}>
                    {hotel.room_type && <span className={styles.selectionBadge}>{hotel.room_type}</span>}
                    {hotel.bed_type && <span className={styles.selectionBadge}>{hotel.bed_type}</span>}
                    {hotel.check_in && hotel.check_out && (
                        <span className={styles.hotelDates}>
                            {hotel.check_in} → {hotel.check_out}
                        </span>
                    )}
                </div>
            </div>
            <div className={styles.selectionCardPrice}>
                {price > 0 ? (
                    <>
                        <span>{formatINR(price)}</span>
                        {perNight > 0 && <span className={styles.perNight}>{formatINR(perNight)}/night</span>}
                    </>
                ) : 'Price on request'}
            </div>
        </motion.button>
    );
}

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
    const [availableFlights, setAvailableFlights] = useState<FlightOption[]>([]);
    const [availableHotels, setAvailableHotels] = useState<HotelOption[]>([]);
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
    }, [messages, reviewItinerary, finalItinerary, availableFlights, availableHotels, scrollToBottom]);

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
        setAvailableFlights([]);
        setAvailableHotels([]);

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
            if (response.status === 'selecting_flight' && response.data?.available_flights) {
                setAvailableFlights(response.data.available_flights);
            }
            if (response.status === 'selecting_hotel' && response.data?.available_hotels) {
                setAvailableHotels(response.data.available_hotels);
            }
            if (response.status === 'reviewing' && response.data?.itinerary) {
                setReviewItinerary(response.data.itinerary);
            }
            if (response.status === 'complete' && response.data?.trip_id) {
                setCompletedTripId(response.data.trip_id);
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

    const handleApprove = () => sendMessage('approve');

    const handleRevise = (feedback: string) => sendMessage(feedback);

    const handleFlightSelect = (idx: number) => {
        setAvailableFlights([]);
        sendMessage(String(idx));
    };

    const handleHotelSelect = (idx: number) => {
        setAvailableHotels([]);
        sendMessage(String(idx));
    };

    const getStatusLabel = () => {
        if (sending) return <><Loader2 size={12} className={styles.spinIcon} /> Planning...</>;
        switch (currentStatus) {
            case 'clarifying': return <><span className={styles.statusDot} /> Gathering details</>;
            case 'selecting_flight': return <><span className={styles.statusDot} /> Choose your flight</>;
            case 'selecting_hotel': return <><span className={styles.statusDot} /> Choose your hotel</>;
            case 'reviewing': return <><span className={styles.statusDot} /> Awaiting review</>;
            case 'complete': return <><span className={styles.statusDot} /> Trip finalized</>;
            default: return <><span className={styles.statusDot} /> Ready to help</>;
        }
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
                        <div className={styles.headerStatus}>{getStatusLabel()}</div>
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

            {/* Messages Area */}
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
                            <p>Tell me about your dream trip and I&apos;ll create a personalized itinerary — with real flight & hotel options in ₹ INR.</p>
                            <div className={styles.quickPrompts}>
                                {[
                                    'Plan a 5-day trip to Tokyo from Mumbai',
                                    'Weekend getaway in Goa for 2',
                                    'Family trip to Bali for a week from Delhi',
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
                                            {msg.status === 'selecting_flight' ? '✈️ Select Your Flight' :
                                                msg.status === 'selecting_hotel' ? '🏨 Select Your Hotel' :
                                                    msg.status === 'reviewing' ? '📋 Review Itinerary Below' :
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

                    {/* ── Flight Selection UI ── */}
                    <AnimatePresence>
                        {availableFlights.length > 0 && (
                            <motion.div
                                className={styles.selectionPanel}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 20 }}
                            >
                                <div className={styles.selectionPanelHeader}>
                                    <Plane size={18} />
                                    <h3>Select Your Flight</h3>
                                    <span className={styles.currencyBadge}>Prices in ₹ INR</span>
                                </div>
                                <div className={styles.selectionCards}>
                                    {availableFlights.map((flight, i) => (
                                        <FlightCard
                                            key={i}
                                            flight={{ ...flight, index: i + 1 }}
                                            onSelect={handleFlightSelect}
                                        />
                                    ))}
                                </div>
                                <p className={styles.selectionHint}>
                                    💡 Economy class assumed. Mention &quot;business class&quot; if needed.
                                </p>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* ── Hotel Selection UI ── */}
                    <AnimatePresence>
                        {availableHotels.length > 0 && (
                            <motion.div
                                className={styles.selectionPanel}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 20 }}
                            >
                                <div className={styles.selectionPanelHeader}>
                                    <Hotel size={18} />
                                    <h3>Select Your Hotel</h3>
                                    <span className={styles.currencyBadge}>Prices in ₹ INR</span>
                                </div>
                                <div className={styles.selectionCards}>
                                    {availableHotels.map((hotel, i) => (
                                        <HotelCard
                                            key={i}
                                            hotel={{ ...hotel, index: i + 1 }}
                                            onSelect={handleHotelSelect}
                                        />
                                    ))}
                                </div>
                                <p className={styles.selectionHint}>
                                    💡 3-star hotel assumed. Mention &quot;luxury&quot; or &quot;budget&quot; if needed.
                                </p>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* ── Itinerary Review (while reviewing) ── */}
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
                                        <IndianRupee size={15} />
                                        {formatINR(reviewItinerary.total_cost_estimate ?? 0)} INR
                                    </div>
                                </div>

                                {/* Selected Flight & Hotel summary */}
                                {(reviewItinerary.selected_flight || reviewItinerary.selected_hotel) && (
                                    <div className={styles.selectionSummary}>
                                        {reviewItinerary.selected_flight && !reviewItinerary.selected_flight.assumption && (
                                            <div className={styles.selectionSummaryItem}>
                                                <Plane size={13} />
                                                <span>
                                                    {reviewItinerary.selected_flight.airline} {reviewItinerary.selected_flight.flight_number} —{' '}
                                                    {formatINR(reviewItinerary.selected_flight.price_inr)}
                                                </span>
                                            </div>
                                        )}
                                        {reviewItinerary.selected_hotel && !reviewItinerary.selected_hotel.assumption && (
                                            <div className={styles.selectionSummaryItem}>
                                                <Hotel size={13} />
                                                <span>
                                                    {reviewItinerary.selected_hotel.name} —{' '}
                                                    {formatINR(reviewItinerary.selected_hotel.price_inr || reviewItinerary.selected_hotel.best_price_inr || 0)} total
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                )}

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
                                                {day.theme && <span className={styles.dayTheme}>{day.theme}</span>}
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
                                                                    {formatINR(act.cost_estimate)}
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

                    {/* ── Final Itinerary (after completion) ── */}
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
                                        <IndianRupee size={15} />
                                        {formatINR(finalItinerary.itinerary.total_cost_estimate ?? 0)} INR
                                    </div>
                                </div>

                                {/* Selected Flight & Hotel summary */}
                                {(finalItinerary.itinerary.selected_flight || finalItinerary.itinerary.selected_hotel) && (
                                    <div className={styles.selectionSummary}>
                                        {finalItinerary.itinerary.selected_flight && !finalItinerary.itinerary.selected_flight.assumption && (
                                            <div className={styles.selectionSummaryItem}>
                                                <Plane size={13} />
                                                <span>
                                                    {finalItinerary.itinerary.selected_flight.airline} {finalItinerary.itinerary.selected_flight.flight_number} —{' '}
                                                    {formatINR(finalItinerary.itinerary.selected_flight.price_inr)}
                                                </span>
                                            </div>
                                        )}
                                        {finalItinerary.itinerary.selected_hotel && !finalItinerary.itinerary.selected_hotel.assumption && (
                                            <div className={styles.selectionSummaryItem}>
                                                <Hotel size={13} />
                                                <span>
                                                    {finalItinerary.itinerary.selected_hotel.name} —{' '}
                                                    {formatINR(finalItinerary.itinerary.selected_hotel.price_inr || finalItinerary.itinerary.selected_hotel.best_price_inr || 0)} total
                                                </span>
                                            </div>
                                        )}
                                    </div>
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
                                                                    {formatINR(act.cost_estimate)}
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
                                : currentStatus === 'selecting_flight'
                                    ? 'Type a number (1, 2, ...) to select a flight...'
                                    : currentStatus === 'selecting_hotel'
                                        ? 'Type a number (1, 2, ...) to select a hotel...'
                                        : currentStatus === 'reviewing'
                                            ? 'Describe any changes, or type "approve"...'
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
