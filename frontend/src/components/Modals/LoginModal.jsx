import React from 'react';
import AuthButton from '../Auth/AuthButton';
import styles from './LoginModal.module.css';

const LoginModal = ({ open, onClose }) => {
  if (!open) return null;

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent}>
        <button className={styles.closeButton} onClick={onClose}>×</button>
        <div className={styles.authContainer}>
          <h2>Войти в систему</h2>
          <div className={styles.authButtons}>
            <AuthButton provider="google" onLogin={() => {}} />
            <AuthButton provider="facebook" onLogin={() => {}} />
            <AuthButton provider="apple" onLogin={() => {}} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginModal;
