'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { usersAPI } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import {
    DollarSign, Compass, Heart, Cloud, Building, UtensilsCrossed,
    ArrowRight, ArrowLeft, Check, Sparkles
} from 'lucide-react';
import styles from './page.module.css';

const TRAVEL_STYLES = ['Adventure', 'Cultural', 'Luxury', 'Budget', 'Romantic', 'Family', 'Solo', 'Backpacking'];
const INTERESTS = ['Hiking', 'Food', 'Photography', 'History', 'Art', 'Nightlife', 'Shopping', 'Wildlife', 'Beaches', 'Mountains', 'Architecture', 'Music', 'Sports', 'Wellness'];
const CLIMATES = ['Tropical', 'Mediterranean', 'Temperate', 'Dry/Arid', 'Cold/Winter', 'Monsoon'];
const ACCOMMODATIONS = ['Hotel', 'Hostel', 'Resort', 'Boutique Hotel', 'Airbnb', 'Camping', 'Villa'];
const FOOD_PREFS = ['Vegetarian', 'Vegan', 'Local Cuisine', 'Street Food', 'Fine Dining', 'Halal', 'Kosher', 'Seafood', 'No Preference'];
const RISK_LEVELS = [
    { value: 'low', label: 'Low', desc: 'Prefer safe, well-known destinations' },
    { value: 'moderate', label: 'Moderate', desc: 'Open to some off-the-beaten-path' },
    { value: 'high', label: 'High', desc: 'Love exploring hidden gems & adventures' },
];

const STEPS = [
    { icon: <DollarSign size={20} />, label: 'Budget' },
    { icon: <Compass size={20} />, label: 'Style' },
    { icon: <Heart size={20} />, label: 'Interests' },
    { icon: <Cloud size={20} />, label: 'Climate' },
    { icon: <Building size={20} />, label: 'Stay' },
    { icon: <UtensilsCrossed size={20} />, label: 'Food' },
];

export default function PreferencesPage() {
    const [step, setStep] = useState(0);
    const [budgetMin, setBudgetMin] = useState(500);
    const [budgetMax, setBudgetMax] = useState(3000);
    const [travelStyle, setTravelStyle] = useState<string[]>([]);
    const [interests, setInterests] = useState<string[]>([]);
    const [climate, setClimate] = useState<string[]>([]);
    const [accommodation, setAccommodation] = useState<string[]>([]);
    const [foodPrefs, setFoodPrefs] = useState<string[]>([]);
    const [riskTolerance, setRiskTolerance] = useState<'low' | 'moderate' | 'high'>('moderate');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const { user, fetchUser } = useAuthStore();
    const router = useRouter();

    // Pre-fill if user already has preferences
    useEffect(() => {
        if (user?.preferences) {
            const p = user.preferences;
            if (p.budget_range?.min) setBudgetMin(p.budget_range.min);
            if (p.budget_range?.max) setBudgetMax(p.budget_range.max);
            if (p.travel_style?.length) setTravelStyle(p.travel_style);
            if (p.interests?.length) setInterests(p.interests);
            if (p.preferred_climate?.length) setClimate(p.preferred_climate);
            if (p.accommodation_type?.length) setAccommodation(p.accommodation_type);
            if (p.food_preferences?.length) setFoodPrefs(p.food_preferences);
            if (p.risk_tolerance) setRiskTolerance(p.risk_tolerance);
        }
    }, [user]);

    const toggleChip = (list: string[], setList: (v: string[]) => void, item: string) => {
        const lower = item.toLowerCase();
        setList(list.includes(lower) ? list.filter((i) => i !== lower) : [...list, lower]);
    };

    const handleSave = async () => {
        setSaving(true);
        setError('');
        try {
            await usersAPI.updatePreferences({
                budget_range: { min: budgetMin, max: budgetMax },
                travel_style: travelStyle,
                interests,
                preferred_climate: climate,
                accommodation_type: accommodation,
                food_preferences: foodPrefs,
                risk_tolerance: riskTolerance,
            });
            await fetchUser();
            router.push('/dashboard');
        } catch {
            setError('Failed to save preferences. Please try again.');
        } finally {
            setSaving(false);
        }
    };

    const canProceed = () => {
        switch (step) {
            case 0: return budgetMin > 0 && budgetMax > budgetMin;
            case 1: return travelStyle.length > 0;
            case 2: return interests.length > 0;
            case 3: return climate.length > 0;
            case 4: return accommodation.length > 0;
            case 5: return foodPrefs.length > 0;
            default: return true;
        }
    };

    const renderStep = () => {
        switch (step) {
            case 0:
                return (
                    <div className={styles.stepContent}>
                        <h2>What&apos;s your budget range?</h2>
                        <p className={styles.stepDesc}>Set your comfortable spending range per trip</p>
                        <div className={styles.budgetInputs}>
                            <div className="input-group">
                                <label className="input-label">Minimum ($)</label>
                                <input
                                    type="number"
                                    className="input"
                                    value={budgetMin}
                                    onChange={(e) => setBudgetMin(Number(e.target.value))}
                                    min={0}
                                />
                            </div>
                            <div className={styles.budgetDivider}>to</div>
                            <div className="input-group">
                                <label className="input-label">Maximum ($)</label>
                                <input
                                    type="number"
                                    className="input"
                                    value={budgetMax}
                                    onChange={(e) => setBudgetMax(Number(e.target.value))}
                                    min={budgetMin + 1}
                                />
                            </div>
                        </div>
                        <div className={styles.riskSection}>
                            <label className="input-label" style={{ marginBottom: 12 }}>Risk Tolerance</label>
                            <div className={styles.riskOptions}>
                                {RISK_LEVELS.map((r) => (
                                    <div
                                        key={r.value}
                                        className={`${styles.riskCard} ${riskTolerance === r.value ? styles.riskCardActive : ''}`}
                                        onClick={() => setRiskTolerance(r.value as 'low' | 'moderate' | 'high')}
                                    >
                                        <div className={styles.riskLabel}>{r.label}</div>
                                        <div className={styles.riskDesc}>{r.desc}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                );
            case 1:
                return (
                    <div className={styles.stepContent}>
                        <h2>Your travel style</h2>
                        <p className={styles.stepDesc}>Select all that describe your ideal vacation</p>
                        <div className={styles.chipGrid}>
                            {TRAVEL_STYLES.map((s) => (
                                <button
                                    key={s}
                                    className={`chip ${travelStyle.includes(s.toLowerCase()) ? 'chip-active' : ''}`}
                                    onClick={() => toggleChip(travelStyle, setTravelStyle, s)}
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                );
            case 2:
                return (
                    <div className={styles.stepContent}>
                        <h2>What interests you?</h2>
                        <p className={styles.stepDesc}>Pick your favorite activities and interests</p>
                        <div className={styles.chipGrid}>
                            {INTERESTS.map((i) => (
                                <button
                                    key={i}
                                    className={`chip ${interests.includes(i.toLowerCase()) ? 'chip-active' : ''}`}
                                    onClick={() => toggleChip(interests, setInterests, i)}
                                >
                                    {i}
                                </button>
                            ))}
                        </div>
                    </div>
                );
            case 3:
                return (
                    <div className={styles.stepContent}>
                        <h2>Climate preference</h2>
                        <p className={styles.stepDesc}>What weather do you enjoy traveling in?</p>
                        <div className={styles.chipGrid}>
                            {CLIMATES.map((c) => (
                                <button
                                    key={c}
                                    className={`chip ${climate.includes(c.toLowerCase()) ? 'chip-active' : ''}`}
                                    onClick={() => toggleChip(climate, setClimate, c)}
                                >
                                    {c}
                                </button>
                            ))}
                        </div>
                    </div>
                );
            case 4:
                return (
                    <div className={styles.stepContent}>
                        <h2>Where do you like to stay?</h2>
                        <p className={styles.stepDesc}>Select your preferred accommodation types</p>
                        <div className={styles.chipGrid}>
                            {ACCOMMODATIONS.map((a) => (
                                <button
                                    key={a}
                                    className={`chip ${accommodation.includes(a.toLowerCase()) ? 'chip-active' : ''}`}
                                    onClick={() => toggleChip(accommodation, setAccommodation, a)}
                                >
                                    {a}
                                </button>
                            ))}
                        </div>
                    </div>
                );
            case 5:
                return (
                    <div className={styles.stepContent}>
                        <h2>Food preferences</h2>
                        <p className={styles.stepDesc}>Any dietary preferences or food interests?</p>
                        <div className={styles.chipGrid}>
                            {FOOD_PREFS.map((f) => (
                                <button
                                    key={f}
                                    className={`chip ${foodPrefs.includes(f.toLowerCase()) ? 'chip-active' : ''}`}
                                    onClick={() => toggleChip(foodPrefs, setFoodPrefs, f)}
                                >
                                    {f}
                                </button>
                            ))}
                        </div>
                    </div>
                );
            default:
                return null;
        }
    };

    return (
        <div className={styles.container}>
            {/* Progress */}
            <div className={styles.progressBar}>
                {STEPS.map((s, i) => (
                    <div
                        key={i}
                        className={`${styles.progressStep} ${i === step ? styles.progressStepActive : ''} ${i < step ? styles.progressStepDone : ''}`}
                        onClick={() => i < step && setStep(i)}
                    >
                        <div className={styles.progressIcon}>
                            {i < step ? <Check size={16} /> : s.icon}
                        </div>
                        <span className={styles.progressLabel}>{s.label}</span>
                    </div>
                ))}
            </div>

            {/* Step Content */}
            <div className={styles.content}>
                <AnimatePresence mode="wait">
                    <motion.div
                        key={step}
                        initial={{ opacity: 0, x: 30 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -30 }}
                        transition={{ duration: 0.25 }}
                    >
                        {renderStep()}
                    </motion.div>
                </AnimatePresence>

                {error && (
                    <div className={styles.errorText}>{error}</div>
                )}

                {/* Navigation */}
                <div className={styles.navButtons}>
                    {step > 0 && (
                        <button className="btn btn-secondary" onClick={() => setStep(step - 1)}>
                            <ArrowLeft size={18} /> Back
                        </button>
                    )}
                    <div style={{ flex: 1 }} />
                    {step < STEPS.length - 1 ? (
                        <button
                            className="btn btn-primary"
                            onClick={() => setStep(step + 1)}
                            disabled={!canProceed()}
                        >
                            Next <ArrowRight size={18} />
                        </button>
                    ) : (
                        <button
                            className="btn btn-primary btn-lg"
                            onClick={handleSave}
                            disabled={saving || !canProceed()}
                        >
                            {saving ? (
                                <span className={styles.spinner} />
                            ) : (
                                <>
                                    <Sparkles size={18} /> Save & Continue
                                </>
                            )}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
