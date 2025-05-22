import styles from './Footer.module.css';

export default function Footer(){
  return(
    <footer className={styles.footer}>
      <div className="container">
        <div className={styles.top}>
          <div>
            <h2>Алтын Ханым</h2>
            <p>Ежегодный конкурс красоты</p>
          </div>
          <div>
            <h3>Быстрые ссылки</h3>
            <ul>
              <li><a href="#">Главная</a></li>
              <li><a href="#contestants">Участницы</a></li>
              <li><a href="#results">Результаты</a></li>
            </ul>
          </div>
          <div>
            <h3>Связаться с нами</h3>
            <div className={styles.social}>
              {['facebook-f','instagram','twitter','youtube','vk'].map(i=>(
                <a key={i} href="#"><i className={`fab fa-${i}`}/></a>
              ))}
            </div>
          </div>
        </div>
        <div className={styles.bottom}>
          &copy; 2025 Алтын Ханым. Все права защищены.
        </div>
      </div>
    </footer>
  );
}
