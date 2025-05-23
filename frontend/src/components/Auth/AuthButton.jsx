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
      if (onLogin) onLogin(data.token);
    } catch (error) {
      console.error('Ошибка при авторизации:', error);
    }
  };

  const getProviderConfig = (provider) => {
    const configs = {
      google: {
        icon: 'fab fa-google',
        text: 'Войти через Google',
        className: 'google'
      },
      apple: {
        icon: 'fab fa-apple',
        text: 'Войти через Apple ID',
        className: 'apple'
      },
      facebook: {
        icon: 'fab fa-facebook-f',
        text: 'Войти через Facebook',
        className: 'facebook'
      },
      instagram: {
        icon: 'fab fa-instagram',
        text: 'Войти через Instagram',
        className: 'instagram'
      }
    };
    return configs[provider] || { icon: '', text: 'Войти', className: '' };
  };

  const config = getProviderConfig(provider);

  return (
    <button 
      className={`${styles.socialBtn} ${styles[config.className]}`}
      onClick={handleClick}
    >
      <i className={config.icon}></i> {config.text}
    </button>
  );
};

export default AuthButton; 