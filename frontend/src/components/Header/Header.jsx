import styles from './Header.module.css';
import logo from '../../assets/logo.svg';

export default function Header({active, openLogin}){
  return(
    <header className={styles.header}>
      <div className={`container ${styles.headerContainer}`}>
        <div className={styles.logo}>
          <img src={logo} alt="Алтын Ханым" className={styles.logoImage}/>
          {/* <div>
            <h1>Алтын Ханым</h1>
            <span className={styles.subtitle}>ГОЛОСОВАНИЕ</span>
          </div> */}
        </div>

        <nav>
          <ul>
            <li><a href="#home" className={active === 'home' ? styles.active : ''}>Главная</a></li>
            <li><a href="#about" className={active === 'about' ? styles.active : ''}>О конкурсе</a></li>
            <li><a href="#contestants" className={active === 'contestants' ? styles.active : ''}>Участницы</a></li>
            <li><a href="#results" className={active === 'results' ? styles.active : ''}>Результаты</a></li>
          </ul>
        </nav>

        <button className={styles.loginBtn} onClick={openLogin}>
          <i className="fas fa-user"></i> Войти
        </button>
      </div>
    </header>
  );
}
