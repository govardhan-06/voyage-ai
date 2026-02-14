import styles from './LoadingSkeleton.module.css';

export function CardSkeleton() {
    return (
        <div className={styles.cardSkeleton}>
            <div className={`skeleton ${styles.skeletonImage}`} />
            <div className={styles.skeletonContent}>
                <div className={`skeleton ${styles.skeletonTitle}`} />
                <div className={`skeleton ${styles.skeletonText}`} />
                <div className={`skeleton ${styles.skeletonTextShort}`} />
            </div>
        </div>
    );
}

export function ChatSkeleton() {
    return (
        <div className={styles.chatSkeleton}>
            <div className={styles.chatBubbleSkeleton}>
                <div className={`skeleton ${styles.skeletonAvatar}`} />
                <div className={styles.chatBubbleContent}>
                    <div className={`skeleton ${styles.skeletonText}`} />
                    <div className={`skeleton ${styles.skeletonTextShort}`} />
                </div>
            </div>
        </div>
    );
}

export function ItinerarySkeleton() {
    return (
        <div className={styles.itinerarySkeleton}>
            {[1, 2, 3].map((i) => (
                <div key={i} className={styles.daySkeleton}>
                    <div className={`skeleton ${styles.skeletonDayHeader}`} />
                    <div className={`skeleton ${styles.skeletonActivity}`} />
                    <div className={`skeleton ${styles.skeletonActivity}`} />
                </div>
            ))}
        </div>
    );
}
