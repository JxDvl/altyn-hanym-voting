import { useState, useEffect } from 'react';
import styles from './Contestants.module.css';
import placeholder from '../../assets/placeholder400x600.jpg';

export default function ContestantCard({data,number,onVote}){
  const {candidate_id,name,description,modal_description,vote_count=0} = data;
  const [img, setImg] = useState(placeholder);
  
  useEffect(() => {
    const loadImage = async () => {
      try {
        const imageModule = await import(`../../assets/${candidate_id}.jpeg`);
        setImg(imageModule.default);
      } catch (error) {
        console.warn(`Изображение для участницы ${candidate_id} не найдено, используется placeholder`);
        setImg(placeholder);
      }
    };
    
    loadImage();
  }, [candidate_id]);

  const handleVote = () => {
    onVote({candidate_id,name,description:modal_description,img});
  };

  return(
    <div className={styles.card}>
      <div className={styles.image}>
        <img src={img} alt={name}/>
        <span className={styles.number}>{number}</span>
      </div>
      <div className={styles.info}>
        <h3>{name}</h3>
        <p>{description || "Участница конкурса"}</p>
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
