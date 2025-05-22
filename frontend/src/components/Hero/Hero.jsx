import React from 'react';
import styles from './Hero.module.css';

const Hero = () => {
  return (
    <section className={styles.hero}>
      <div className={styles.decor}>
        <div className={`${styles.circle} ${styles.circle1}`}></div>
        <div className={`${styles.circle} ${styles.circle2}`}></div>
        <div className={`${styles.circle} ${styles.circle3}`}></div>
        <div className={`${styles.sparkle} ${styles.sparkle1}`}></div>
        <div className={`${styles.sparkle} ${styles.sparkle2}`}></div>
        <div className={`${styles.sparkle} ${styles.sparkle3}`}></div>
        <div className={`${styles.sparkle} ${styles.sparkle4}`}></div>
        <div className={`${styles.sparkle} ${styles.sparkle5}`}></div>
      </div>
      <div>
        <h1>КОНКУРС КРАСОТЫ</h1>
        <h2>АЛТЫН ХАНЫМ</h2>
        <p>
          Примите участие в голосовании за участниц конкурса красоты "Алтын Ханым".
          Ваш голос может решить судьбу конкурса!
        </p>
        <a href="#contestants" className={styles.ctaButton}>Голосовать сейчас</a>
      </div>
    </section>
  );
};

export default Hero;
