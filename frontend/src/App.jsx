import { useRef, useState } from 'react';
import Header from './components/Header/Header';
import Hero from './components/Hero/Hero';
import ContestantGrid from './components/Contestants/ContestantGrid';
import Footer from './components/Footer/Footer';
import LoginModal from './components/Modals/LoginModal';
import VoteConfirmModal from './components/Modals/VoteConfirmModal';
import useActiveSection from './hooks/useActiveSection';

export default function App() {
  const sections = { home:useRef(), contestants:useRef(), results:useRef() };
  const active = useActiveSection(sections);

  const [loginOpen,setLoginOpen] = useState(false);
  const [voteData,setVoteData] = useState(null);

  return (
    <>
      <Header active={active} openLogin={()=>setLoginOpen(true)} />

      <main>
        <section ref={sections.home} id="home"><Hero/></section>
        <section ref={sections.contestants} id="contestants">
          <ContestantGrid openVote={setVoteData}/>
        </section>
      </main>

      <Footer/>

      <LoginModal open={loginOpen} onClose={()=>setLoginOpen(false)}/>
      <VoteConfirmModal data={voteData} onClose={()=>setVoteData(null)}/>
    </>
  );
}
