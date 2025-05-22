import React from 'react';
import styles from './AuthButton.module.css';

const AuthButton = ({ provider, onLogin }) => {
  const handleClick = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/auth/${provider}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error('Ошибка авторизации');
      }
      
      const data = await response.json();
      localStorage.setItem('auth_token', data.token);
      onLogin(data.token);
    } catch (error) {
      console.error('Ошибка при авторизации:', error);
    }
  };

  return (
    <button 
      className={styles.authButton}
      onClick={handleClick}
    >
      Войти через {provider.charAt(0).toUpperCase() + provider.slice(1)}
    </button>
  );
};

export default AuthButton; 