import styles from './Contestants.module.css';
import placeholder from '../../assets/placeholder400x600.jpg';

export default function ContestantCard({data,number,onVote}){
  const {candidate_id,name,vote_count=0} = data;
  const img = placeholder;             // здесь подставьте реальное фото

  const handleVote = () => {
    onVote({candidate_id,name,img});
  };

  return(
    <div className={styles.card}>
      <div className={styles.image}>
        <img src={img} alt={name}/>
        <span className={styles.number}>{number}</span>
      </div>
      <div className={styles.info}>
        <h3>{name}</h3>
        <p>Возраст / город</p>
        <button className={styles.voteBtn} onClick={handleVote}>
          Голосовать
        </button>
        <div className={styles.results}>
          Проголосовало: <span className={styles.count}>{vote_count}</span> человек
        </div>
      </div>
    </div>
  );
}
