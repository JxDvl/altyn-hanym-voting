import React from 'react';
import AuthButton from '../Auth/AuthButton';
import styles from './LoginModal.module.css';

const LoginModal = ({ open, onClose }) => {
  if (!open) return null;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div className={styles.modal} onClick={handleOverlayClick}>
      <div className={styles.modalContent}>
        <span className={styles.closeBtn} onClick={onClose}>&times;</span>
        <h2>Авторизация</h2>
        <p>Пожалуйста, авторизуйтесь через одну из социальных сетей, чтобы проголосовать за участницу:</p>
        <div className={styles.socialLogin}>
          <AuthButton provider="google" />
          <AuthButton provider="apple" />
          <AuthButton provider="facebook" />
          <AuthButton provider="instagram" />
        </div>
      </div>
    </div>
  );
};

export default LoginModal;
