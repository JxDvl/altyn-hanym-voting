import styles from './Modals.module.css';

export default function VoteConfirmModal({data,onClose}){
  if(!data) return null;
  const {candidate_id,name,img} = data;

  async function confirm(){
    try{
      const token = localStorage.getItem('token');
      if(!token) {
        alert('Пожалуйста, авторизуйтесь для голосования');
        onClose();
        return;
      }

      const res = await fetch(import.meta.env.VITE_API_URL+'/vote',{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          'Authorization':`Bearer ${token}`
        },
        body:JSON.stringify({candidate_id})
      });

      if(res.ok) {
        alert('Ваш голос принят!');
        onClose();
      } else {
        const error = await res.json();
        if(error.code === 'ALREADY_VOTED') {
          alert('Вы уже проголосовали ранее');
        } else {
          alert('Ошибка: '+error.detail);
        }
      }
    } catch(err) {
      console.error(err);
      alert('Сервер недоступен');
    }
  }

  return(
    <div className={styles.modal} style={{display: 'flex'}}>
      <div className={styles.content}>
        <span className={styles.close} onClick={onClose}>&times;</span>
        <h2>Подтверждение голосования</h2>
        <div className={styles.voteBlock}>
          <img src={img} alt={name}/>
          <div>
            <h3>{name}</h3>
            <p>№{candidate_id}</p>
          </div>
        </div>
        <p className={styles.warning}>Внимание! Вы можете голосовать только один раз.</p>
        <div className={styles.actions}>
          <button className={styles.cancel} onClick={onClose}>Отменить</button>
          <button className={styles.confirm} onClick={confirm}>Подтвердить</button>
        </div>
      </div>
    </div>
  );
}
