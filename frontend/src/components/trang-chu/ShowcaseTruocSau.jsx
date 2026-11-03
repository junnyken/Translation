import { useState } from 'react'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'

const NOI_DUNG_SHOWCASE = {
  vi: {
    badge: '✨ TRẢI NGHIỆM CHẤT LƯỢNG THỰC TẾ TRƯỚC & SAU KHI DỊCH',
    title: 'So Sánh Trực Quan: Xoá Chữ LaMa & Dàn Chữ Thông Minh',
    subtitle:
      'Kéo thanh trượt sang trái/phải để xem cách AI tự động xoá sạch chữ gốc trên nền phức tạp và dàn bản dịch khớp hoàn hảo vào bong bóng.',
    beforeLabel: 'TRƯỚC (RAW GỐC)',
    afterLabel: 'SAU (ĐÃ DỊCH AI)',
    sliderAria: 'Kéo để so sánh trang gốc và trang đã dịch',
    samples: [
      {
        id: 'manga_jp',
        tab: '🇯🇵 Manga Nhật (Chữ dọc)',
        genre: '⚔️ Hành động · Đen trắng Screentone',
        rawTop: 'まさか…あの一撃を\n無傷で受け止めたのか！？',
        rawBot: '面白い…！\n全力で行くぞ！！',
        transTop: 'Không thể nào… Hắn đỡ trọn\nđòn chí mạng đó mà không hề hấn gì sao!?',
        transBot: 'Thú vị đấy…!\nTa sẽ tung toàn lực đây!!',
        sfxRaw: 'ドゴォン!!',
        sfxNote: 'Giữ nguyên hiệu ứng âm thanh (SFX) nghệ thuật',
      },
      {
        id: 'manhwa_kr',
        tab: '🇰🇷 Manhwa Hàn (Webtoon màu)',
        genre: '🔥 Hệ thống / Hunter · Nền chuyển sắc',
        rawTop: '[시스템 알림]\n그림자 군주의 권능이 각성합니다.',
        rawBot: '일어나라.\n나의 병사들이여.',
        transTop: '[THÔNG BÁO HỆ THỐNG]\nQuyền năng Quân Vương Bóng Tối đã thức tỉnh.',
        transBot: 'Hãy trỗi dậy đi.\nHỡi những binh lính của ta.',
        sfxRaw: '쿠구구궁—!',
        sfxNote: 'Tái tạo nền màu Gradient không để lại vết xoá',
      },
      {
        id: 'manhua_zh',
        tab: '🇨🇳 Manhua Trung (Tu tiên)',
        genre: '🏮 Cổ trang / Tu tiên · Font thư pháp',
        rawTop: '区区筑基期修士，\n也敢在本尊面前放肆？',
        rawBot: '今日便让你见识一下，\n何为真正的天道剑意！',
        transTop: 'Chỉ là một tu sĩ Trúc Cơ kỳ nhỏ nhoi,\ncũng dám ngông cuồng trước mặt Bản tôn sao?',
        transBot: 'Hôm nay ta sẽ cho ngươi mở tầm mắt,\nthế nào là Thiên Đạo Kiếm Ý thực sự!',
        sfxRaw: '轰隆—',
        sfxNote: 'Chuẩn xưng hô Cổ trang (Bản tôn - Ngươi)',
      },
    ],
    faqTitle: 'Câu Hỏi Thường Gặp (FAQ)',
    faqSub: 'Giải đáp chi tiết về công nghệ dịch truyện tranh AI, bảo mật và định dạng hỗ trợ.',
    faqs: [
      {
        q: 'Làm sao để dịch truyện tranh Raw (Nhật, Hàn, Trung) tự động mà không biết ngoại ngữ?',
        a: 'Bạn chỉ cần kéo thả ảnh trang truyện (PNG, JPG, WebP) hoặc gói cả chương (.ZIP, .CBZ, .PDF) vào ô tải lên, chọn ngôn ngữ gốc và ngôn ngữ đích (Tiếng Việt, Tiếng Anh, Tây Ban Nha, Bồ Đào Nha, Pháp...). AI sẽ tự động nhận diện khung thoại, xoá chữ gốc bằng mô hình LaMa và chèn bản dịch trong ~3 giây.',
      },
      {
        q: 'Làm thế nào để giữ đồng nhất tên nhân vật và đại từ xưng hô xuyên suốt các chương?',
        a: 'Bạn có thể mở mục "Sổ tay Nhân vật & Xưng hô cố định" ngay dưới ô chọn ngôn ngữ để chọn mẫu xưng hô (Cổ trang Ta-Ngươi, Ngôn tình Anh-Em, hoặc Hunter Tôi-Cậu) và ghi chú tên riêng. Ở chế độ Tạo Chapter, hệ thống còn có bộ kiểm tra nhất quán tự động xuyên chương.',
      },
      {
        q: 'Tôi muốn dịch trực tiếp ngay trên web đọc truyện nước ngoài thì làm thế nào?',
        a: 'Hãy cài đặt Tiện ích Chrome (Live Browser Extension) hoặc App Windows Tự Động của chúng tôi. Chỉ cần bấm tổ hợp phím Alt+Q ngay trên trang đọc truyện bất kỳ, tiện ích sẽ dịch và phủ chữ sắc nét ngay lập tức mà không cần tải ảnh về máy.',
      },
      {
        q: 'Lượt mua thêm (Credits) có bị hết hạn qua đêm không?',
        a: 'Hoàn toàn KHÔNG. Mọi tài khoản đăng ký đều được tặng 10 trang miễn phí mỗi ngày (hồi lại lúc 00:00). Các gói lượt bạn mua thêm sẽ được tích luỹ vĩnh viễn trong ví tài khoản và dùng chung trên cả Website, Tiện ích Chrome, App Windows và Developer API.',
      },
    ],
  },
  en: {
    badge: '✨ INTERACTIVE BEFORE & AFTER TRANSLATION SHOWCASE',
    title: 'Visual Comparison: LaMa Text Removal & Smart Typesetting',
    subtitle:
      'Drag the slider left or right to see how our AI cleanly erases complex vertical/color source text and typesets translations naturally inside speech bubbles.',
    beforeLabel: 'BEFORE (RAW SOURCE)',
    afterLabel: 'AFTER (AI TRANSLATED)',
    sliderAria: 'Drag to compare raw original page and AI translated page',
    samples: [
      {
        id: 'manga_jp',
        tab: '🇯🇵 Japanese Manga (Vertical)',
        genre: '⚔️ Shonen Action · Monochrome Screentone',
        rawTop: 'まさか…あの一撃を\n無傷で受け止めたのか！？',
        rawBot: '面白い…！\n全力で行くぞ！！',
        transTop: 'No way… He tanked that\nultimate strike without a scratch!?',
        transBot: 'Interesting…!\nI’m going all out!!',
        sfxRaw: 'ドゴォン!!',
        sfxNote: 'Preserves artistic SFX & screentone patterns',
      },
      {
        id: 'manhwa_kr',
        tab: '🇰🇷 Korean Manhwa (Webtoon)',
        genre: '🔥 System / Hunter · Full-Color Gradient',
        rawTop: '[시스템 알림]\n그림자 군주의 권능이 각성합니다.',
        rawBot: '일어나라.\n나의 병사들이여.',
        transTop: '[SYSTEM NOTIFICATION]\nThe authority of the Shadow Monarch awakens.',
        transBot: 'Arise,\nmy soldiers.',
        sfxRaw: '쿠구구궁—!',
        sfxNote: 'Seamless gradient background reconstruction',
      },
      {
        id: 'manhua_zh',
        tab: '🇨🇳 Chinese Manhua (Cultivation)',
        genre: '🏮 Martial Arts / Wuxia · Glossary Locked',
        rawTop: '区区筑基期修士，\n也敢在本尊面前放肆？',
        rawBot: '今日便让你见识一下，\n何为真正的天道剑意！',
        transTop: 'A mere Foundation Establishment cultivator\ndares act so arrogantly before This Sovereign?',
        transBot: 'Today you shall witness\nthe true might of the Heavenly Dao Sword Intent!',
        sfxRaw: '轰隆—',
        sfxNote: 'Consistent martial-arts terminology & pronouns',
      },
    ],
    faqTitle: 'Frequently Asked Questions (FAQ)',
    faqSub: 'Everything you need to know about AI manga translation, supported formats, and privacy.',
    faqs: [
      {
        q: 'How can I read and translate raw manga or webtoons online if I don’t know Japanese or Korean?',
        a: 'Simply drop your raw manga images (PNG, JPG, WebP) or full chapter archives (.ZIP, .CBZ, .PDF) into the upload box above. Select the source language (Japanese, Korean, Chinese) and your target language (English, Spanish, Portuguese, French, Vietnamese, etc.). Our multimodal AI detects bubbles, removes original text via LaMa inpainting, and typesets the translation in ~3 seconds.',
      },
      {
        q: 'How does the tool keep character names and honorifics consistent across chapters?',
        a: 'Open the "Character & Pronoun Glossary" right below the language selectors to define character names, ranks, and speaking styles. Our Context AI engine reads the entire page flow and previous page context to ensure natural, consistent dialogue.',
      },
      {
        q: 'Can I translate manga directly on raw reading websites without downloading images?',
        a: 'Yes! Install our Chrome/Edge Browser Extension or Windows Desktop Batch App. Press Alt+Q on any manga or webtoon site to overlay crisp translations directly onto the page as you scroll.',
      },
      {
        q: 'Do purchased page credits expire?',
        a: 'Never. Every registered user gets 10 free pages daily (resets at 00:00 GMT+7). Any credit packs or plans you purchase are stored permanently in your wallet and shared across Web, Browser Extension, Windows App, and Developer API.',
      },
    ],
  },
  es: {
    badge: '✨ DEMOSTRACIÓN INTERACTIVA ANTES Y DESPUÉS',
    title: 'Comparación Visual: Limpieza LaMa y Tipografía Inteligente',
    subtitle:
      'Desliza la barra hacia la izquierda o derecha para ver cómo la IA borra el texto original y maqueta la traducción en español dentro de los bocadillos.',
    beforeLabel: 'ANTES (RAW ORIGINAL)',
    afterLabel: 'DESPUÉS (TRADUCIDO CON IA)',
    sliderAria: 'Deslizar para comparar página original y traducida',
    samples: [
      {
        id: 'manga_jp',
        tab: '🇯🇵 Manga Japonés (Vertical)',
        genre: '⚔️ Acción Shonen · Tramas Blanco y Negro',
        rawTop: 'まさか…あの一撃を\n無傷で受け止めたのか！？',
        rawBot: '面白い…！\n全力で行くぞ！！',
        transTop: '¡¿Imposible… Detuvo ese ataque\ndefinitivo sin un solo rasguño?!',
        transBot: '¡Qué interesante…!\n¡¡Iré con todo mi poder!!',
        sfxRaw: 'ドゴォン!!',
        sfxNote: 'Conserva los efectos de sonido (SFX) y el arte original',
      },
      {
        id: 'manhwa_kr',
        tab: '🇰🇷 Manhwa Coreano (Webtoon)',
        genre: '🔥 Sistema / Cazadores · Color Degradado',
        rawTop: '[시스템 알림]\n그림자 군주의 권능이 각성합니다.',
        rawBot: '일어나라.\n나의 병사들이여.',
        transTop: '[NOTIFICACIÓN DEL SISTEMA]\nLa autoridad del Monarca de las Sombras despierta.',
        transBot: 'Levántense,\nmis soldados.',
        sfxRaw: '쿠구구궁—!',
        sfxNote: 'Reconstrucción perfecta de fondos a color',
      },
      {
        id: 'manhua_zh',
        tab: '🇨🇳 Manhua Chino (Cultivo)',
        genre: '🏮 Artes Marciales / Wuxia · Glosario Fijo',
        rawTop: '区区筑基期修士，\n也敢在本尊面前放肆？',
        rawBot: '今日便让你见识一下，\n何为真正的天道剑意！',
        transTop: '¿Un simple cultivador de Establecimiento de Fundación\nse atreve a ser tan arrogante ante Este Soberano?',
        transBot: '¡Hoy presenciarás el verdadero poder\nde la Intención de Espada del Dao Celestial!',
        sfxRaw: '轰隆—',
        sfxNote: 'Terminología de cultivo y nombres coherentes',
      },
    ],
    faqTitle: 'Preguntas Frecuentes sobre el Traductor de Manga IA (FAQ)',
    faqSub: 'Todo lo que necesitas saber para traducir manga raw, manhwa y webtoons al español.',
    faqs: [
      {
        q: '¿Cómo traducir manga raw, manhwa o webtoons al español gratis con IA?',
        a: 'Solo arrastra tus imágenes (PNG, JPG, WebP) o archivos de capítulo (.ZIP, .CBZ, .PDF) al cuadro de carga, selecciona el idioma original (Japonés, Coreano, Chino) y elige Español como destino. Nuestra IA detecta los bocadillos, borra el texto con LaMa y coloca la traducción en segundos.',
      },
      {
        q: '¿Puedo traducir páginas directamente mientras leo en sitios web de manga?',
        a: '¡Sí! Con nuestra Extensión para Chrome/Edge y la App para Windows puedes traducir cualquier página web en tiempo real presionando Alt+Q, o descargar capítulos completos automáticamente.',
      },
      {
        q: '¿Cómo mantener consistentes los nombres de personajes y términos en todo el capítulo?',
        a: 'Usa el "Glosario de Personajes y Pronombres" antes de traducir para fijar nombres propios y estilos de habla. Además, puedes hacer doble clic sobre cualquier bocadillo para editar el texto manualmente.',
      },
      {
        q: '¿Los créditos comprados caducan?',
        a: 'Nunca caducan. Además de las 10 páginas gratuitas diarias para cuentas registradas, tus paquetes de páginas se guardan para siempre y funcionan en Web, Extensión, App de Windows y API.',
      },
    ],
  },
  pt: {
    badge: '✨ DEMONSTRAÇÃO INTERATIVA ANTES E DEPOIS',
    title: 'Comparação Visual: Limpeza LaMa e Diagramação Inteligente',
    subtitle:
      'Arraste o controle deslizante para ver como nossa IA apaga o texto original em japonês/coreano e insere a tradução em português perfeitamente nos balões.',
    beforeLabel: 'ANTES (RAW ORIGINAL)',
    afterLabel: 'DEPOIS (TRADUZIDO POR IA)',
    sliderAria: 'Arraste para comparar a página original e a traduzida',
    samples: [
      {
        id: 'manga_jp',
        tab: '🇯🇵 Mangá Japonês (Vertical)',
        genre: '⚔️ Ação Shonen · Retículas Preto e Branco',
        rawTop: 'まさか…あの一撃を\n無傷で受け止めたのか！？',
        rawBot: '面白い…！\n全力で行くぞ！！',
        transTop: 'Impossível… Ele bloqueou aquele golpe\nfinal sem nenhum arranhão!?',
        transBot: 'Interessante…!\nVou usar toda a minha força!!',
        sfxRaw: 'ドゴォン!!',
        sfxNote: 'Preserva as onomatopeias (SFX) e o traço original',
      },
      {
        id: 'manhwa_kr',
        tab: '🇰🇷 Manhwa Coreano (Webtoon)',
        genre: '🔥 Sistema / Caçadores · Cores e Degradês',
        rawTop: '[시스템 알림]\n그림자 군주의 권능이 각성합니다.',
        rawBot: '일어나라.\n나의 병사들이여.',
        transTop: '[NOTIFICAÇÃO DO SISTEMA]\nA autoridade do Monarca das Sombras despertou.',
        transBot: 'Ergam-se,\nmeus soldados.',
        sfxRaw: '쿠구구궁—!',
        sfxNote: 'Reconstrução limpa de fundos coloridos com IA LaMa',
      },
      {
        id: 'manhua_zh',
        tab: '🇨🇳 Manhua Chinês (Cultivo)',
        genre: '🏮 Artes Marciais / Wuxia · Glossário Fixo',
        rawTop: '区区筑基期修士，\n也敢在本尊面前放肆？',
        rawBot: '今日便让你见识一下，\n何为真正的天道剑意！',
        transTop: 'Um mero cultivador do Estabelecimento de Fundação\nousa agir com tanta arrogância diante Deste Soberano?',
        transBot: 'Hoje você verá o verdadeiro poder\nda Intenção da Espada do Dao Celestial!',
        sfxRaw: '轰隆—',
        sfxNote: 'Termos e nomes consistentes em todos os capítulos',
      },
    ],
    faqTitle: 'Perguntas Frequentes — Tradutor de Mangá IA (FAQ)',
    faqSub: 'Saiba como traduzir mangá raw, manhwa e webtoon online grátis para português.',
    faqs: [
      {
        q: 'Como traduzir mangá raw, manhwa ou webtoon online grátis com IA?',
        a: 'Basta arrastar as páginas (PNG, JPG, WebP) ou pacotes de capítulos (.ZIP, .CBZ, .PDF) para a área de upload, escolher o idioma original (Japonês, Coreano, Chinês) e selecionar Português (Brasil). A IA detecta os balões, apaga o texto original e diagrama a tradução em ~3 segundos.',
      },
      {
        q: 'Posso traduzir direto nos sites de leitura sem baixar as imagens?',
        a: 'Sim! Instale nossa Extensão para Chrome/Edge ou o Aplicativo Windows. Pressione Alt+Q em qualquer site de mangá ou webtoon para traduzir a página em tempo real enquanto rola a tela.',
      },
      {
        q: 'Como manter os nomes dos personagens padronizados durante todo o capítulo?',
        a: 'Use o "Glossário de Personagens e Pronomes" para fixar termos e nomes próprios. Você também pode dar um duplo clique em qualquer balão para editar a frase manualmente.',
      },
      {
        q: 'As páginas compradas expiram?',
        a: 'Não expiram nunca. Além das 10 páginas grátis por dia para contas cadastradas, qualquer pacote adquirido fica salvo permanentemente na sua carteira para usar na Web, Extensão, App Windows e API.',
      },
    ],
  },
  fr: {
    badge: '✨ DÉMONSTRATION INTERACTIVE AVANT / APRÈS',
    title: 'Comparaison Visuelle : Nettoyage LaMa & Lettrage Intelligent',
    subtitle:
      'Faites glisser le curseur pour voir comment notre IA efface le texte japonais/coréen original et intègre la traduction française dans les bulles.',
    beforeLabel: 'AVANT (RAW ORIGINAL)',
    afterLabel: 'APRÈS (TRADUIT PAR IA)',
    sliderAria: 'Glisser pour comparer la page originale et la page traduite',
    samples: [
      {
        id: 'manga_jp',
        tab: '🇯🇵 Manga Japonais (Vertical)',
        genre: '⚔️ Action Shonen · Trames Noir & Blanc',
        rawTop: 'まさか…あの一撃を\n無傷で受け止めたのか！？',
        rawBot: '面白い…！\n全力で行くぞ！！',
        transTop: 'Impossible… Il a encaissé cette attaque\nultime sans la moindre égratignure !?',
        transBot: 'Intéressant… !\nJe vais me battre à fond !!',
        sfxRaw: 'ドゴォン!!',
        sfxNote: 'Préserve les onomatopées (SFX) et les trames',
      },
      {
        id: 'manhwa_kr',
        tab: '🇰🇷 Manhwa Coréen (Webtoon)',
        genre: '🔥 Système / Chasseurs · Couleurs & Dégradés',
        rawTop: '[시스템 알림]\n그림자 군주의 권능이 각성합니다.',
        rawBot: '일어나라.\n나의 병사들이여.',
        transTop: '[NOTIFICATION SYSTÈME]\nL’autorité du Monarque des Ombres s’éveille.',
        transBot: 'Levez-vous,\nmes soldats.',
        sfxRaw: '쿠구구궁—!',
        sfxNote: 'Reconstruction nette des fonds colorés par IA LaMa',
      },
      {
        id: 'manhua_zh',
        tab: '🇨🇳 Manhua Chinois (Cultivation)',
        genre: '🏮 Arts Martiaux / Wuxia · Glossaire Fixe',
        rawTop: '区区筑基期修士，\n也敢在本尊面前放肆？',
        rawBot: '今日便让你见识一下，\n何为真正的天道剑意！',
        transTop: 'Un simple cultivateur de l’Établissement des Fondations\nose agir avec une telle arrogance devant Ce Souverain ?',
        transBot: 'Aujourd’hui, tu vas découvrir la véritable puissance\nde l’Intention d’Épée du Dao Céleste !',
        sfxRaw: '轰隆—',
        sfxNote: 'Terminologie et noms cohérents sur tout le chapitre',
      },
    ],
    faqTitle: 'Questions Fréquentes — Traducteur de Manga IA (FAQ)',
    faqSub: 'Tout savoir sur la traduction automatique de scans manga, manhwa et webtoons.',
    faqs: [
      {
        q: 'Comment traduire des scans manga raw ou webtoons en ligne gratuitement ?',
        a: 'Glissez simplement vos images (PNG, JPG, WebP) ou archives de chapitres (.ZIP, .CBZ, .PDF) dans la zone d’envoi, choisissez la langue source (Japonais, Coréen, Chinois) et sélectionnez Français. Notre IA détecte les bulles, efface le texte via LaMa et applique le lettrage en ~3 secondes.',
      },
      {
        q: 'Puis-je traduire directement sur mes sites de lecture de scans ?',
        a: 'Oui ! Installez notre Extension Chrome/Edge ou notre Application Windows. Appuyez sur Alt+Q sur n’importe quel site de manga ou webtoon pour traduire la page en direct.',
      },
      {
        q: 'Les crédits de pages achetés expirent-ils ?',
        a: 'Jamais. En plus des 10 pages gratuites par jour pour chaque compte inscrit, vos packs de pages sont conservés à vie et partagés entre le Web, l’Extension, l’App Windows et l’API.',
      },
    ],
  },
}

export default function ShowcaseTruocSau() {
  const { lang } = useNgonNguUI()
  const t = NOI_DUNG_SHOWCASE[lang] || NOI_DUNG_SHOWCASE.en
  const [mauIdx, setMauIdx] = useState(0)
  const [viTriKeo, setViTriKeo] = useState(52)

  const mau = t.samples[mauIdx] || t.samples[0]
  const laManhwa = mau.id === 'manhwa_kr'
  const laManhua = mau.id === 'manhua_zh'

  const nenPanel = laManhwa
    ? 'linear-gradient(145deg, #0f172a 0%, #1e1b4b 52%, #311042 100%)'
    : laManhua
      ? 'linear-gradient(145deg, #1c1917 0%, #292524 55%, #451a03 100%)'
      : 'repeating-radial-gradient(circle at 20% 30%, rgba(148,163,184,0.14) 0, rgba(148,163,184,0.14) 2px, transparent 2px, transparent 8px), linear-gradient(160deg, #1e293b 0%, #0f172a 100%)'

  const renderPanel = (laBanDich) => (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: nenPanel,
        position: 'relative',
        padding: '24px 20px',
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        color: '#f8fafc',
        userSelect: 'none',
      }}
    >
      {/* Nhãn góc */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 2 }}>
        <span
          style={{
            background: laBanDich ? '#059669' : '#dc2626',
            color: '#ffffff',
            fontSize: 11,
            fontWeight: 800,
            padding: '4px 10px',
            borderRadius: 999,
            letterSpacing: 0.4,
            boxShadow: '0 4px 12px rgba(0,0,0,0.35)',
          }}
        >
          {laBanDich ? t.afterLabel : t.beforeLabel}
        </span>
        <span
          style={{
            background: 'rgba(15, 23, 42, 0.78)',
            border: '1px solid rgba(148, 163, 184, 0.35)',
            color: '#e2e8f0',
            fontSize: 11.5,
            fontWeight: 600,
            padding: '3px 10px',
            borderRadius: 999,
          }}
        >
          {mau.genre}
        </span>
      </div>

      {/* Khung tranh & Bong bóng thoại */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 16,
          alignItems: 'center',
          my: 'auto',
          zIndex: 2,
          padding: '12px 4px',
        }}
      >
        {/* Bong bóng 1 */}
        <div
          style={{
            background: laManhwa ? 'rgba(15, 23, 42, 0.92)' : '#ffffff',
            color: laManhwa ? '#38bdf8' : '#0f172a',
            border: laManhwa ? '2px solid #38bdf8' : '2.5px solid #0f172a',
            borderRadius: laManhwa ? 12 : '50% 50% 48% 52% / 44% 46% 54% 56%',
            padding: '18px 16px',
            textAlign: 'center',
            boxShadow: '0 10px 25px rgba(0,0,0,0.35)',
            minHeight: 110,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: laBanDich ? 13.5 : 15,
              fontWeight: 800,
              lineHeight: 1.45,
              whiteSpace: 'pre-line',
              fontFamily: laManhua && laBanDich ? 'serif' : 'inherit',
            }}
          >
            {laBanDich ? mau.transTop : mau.rawTop}
          </p>
        </div>

        {/* Hiệu ứng SFX + Bong bóng 2 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
          <div
            style={{
              fontSize: 22,
              fontWeight: 900,
              color: '#f97316',
              textShadow: '2px 2px 0 #000, -1px -1px 0 #000',
              transform: 'rotate(-6deg)',
              letterSpacing: 1,
            }}
          >
            {mau.sfxRaw}
          </div>
          <div
            style={{
              background: '#ffffff',
              color: '#0f172a',
              border: '2.5px solid #0f172a',
              borderRadius: '48% 52% 45% 55% / 50% 45% 55% 50%',
              padding: '16px 14px',
              textAlign: 'center',
              boxShadow: '0 10px 25px rgba(0,0,0,0.35)',
              width: '100%',
              boxSizing: 'border-box',
            }}
          >
            <p
              style={{
                margin: 0,
                fontSize: laBanDich ? 13.5 : 15,
                fontWeight: 800,
                lineHeight: 1.45,
                whiteSpace: 'pre-line',
              }}
            >
              {laBanDich ? mau.transBot : mau.rawBot}
            </p>
          </div>
        </div>
      </div>

      {/* Ghi chú chân khung */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 12,
          color: '#cbd5e1',
          background: 'rgba(2, 6, 23, 0.65)',
          padding: '6px 12px',
          borderRadius: 8,
          zIndex: 2,
        }}
      >
        <span>✨ {mau.sfxNote}</span>
        <span style={{ color: '#38bdf8', fontWeight: 700 }}>
          {laBanDich ? 'LaMa Inpaint + Smart Fit ✓' : 'Raw Scan'}
        </span>
      </div>
    </div>
  )

  return (
    <section
      className="showcase-truoc-sau"
      aria-labelledby="tieu-de-showcase"
      style={{ margin: '28px 0', display: 'flex', flexDirection: 'column', gap: 28 }}
    >
      {/* Khối 1: Before / After Slider */}
      <div
        style={{
          background: 'var(--nen-the, #ffffff)',
          border: '1.5px solid var(--vien, #e2e8f0)',
          borderRadius: 18,
          padding: '24px 20px',
          boxShadow: '0 10px 30px rgba(15, 23, 42, 0.06)',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: 760, margin: '0 auto 18px' }}>
          <span
            style={{
              display: 'inline-block',
              fontSize: 11.5,
              fontWeight: 800,
              color: '#d9460f',
              background: 'rgba(217, 70, 15, 0.1)',
              padding: '4px 12px',
              borderRadius: 999,
              marginBottom: 8,
            }}
          >
            {t.badge}
          </span>
          <h2 id="tieu-de-showcase" style={{ margin: '0 0 8px', fontSize: 22 }}>
            {t.title}
          </h2>
          <p style={{ margin: 0, fontSize: 14, color: 'var(--mo, #64748b)', lineHeight: 1.55 }}>
            {t.subtitle}
          </p>
        </div>

        {/* Các tab chọn mẫu Manga / Manhwa / Manhua */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 8,
            flexWrap: 'wrap',
            marginBottom: 16,
          }}
        >
          {t.samples.map((s, idx) => (
            <span
              key={s.id}
              role="tab"
              tabIndex={0}
              aria-selected={mauIdx === idx}
              onClick={() => setMauIdx(idx)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setMauIdx(idx)
              }}
              style={{
                padding: '7px 14px',
                borderRadius: 999,
                fontSize: 13,
                fontWeight: 700,
                cursor: 'pointer',
                border: mauIdx === idx ? '1.5px solid #d9460f' : '1.5px solid var(--vien, #cbd5e1)',
                background: mauIdx === idx ? '#d9460f' : 'transparent',
                color: mauIdx === idx ? '#ffffff' : 'var(--chu, #1e293b)',
                transition: 'all 0.15s ease',
              }}
            >
              {s.tab}
            </span>
          ))}
        </div>

        {/* Khung kéo Before / After */}
        <div
          style={{
            position: 'relative',
            maxWidth: 780,
            height: 290,
            margin: '0 auto',
            borderRadius: 14,
            overflow: 'hidden',
            border: '2px solid #0f172a',
            boxShadow: '0 14px 35px rgba(15, 23, 42, 0.18)',
          }}
        >
          {/* Lớp dưới: SAU KHI DỊCH (100% chiều rộng) */}
          <div style={{ position: 'absolute', inset: 0 }}>{renderPanel(true)}</div>

          {/* Lớp trên: TRƯỚC KHI DỊCH (cắt theo phần trăm viTriKeo) */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              clipPath: `inset(0 ${100 - viTriKeo}% 0 0)`,
            }}
          >
            {renderPanel(false)}
          </div>

          {/* Đường kẻ chia & Nút kéo ở giữa */}
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${viTriKeo}%`,
              width: 3,
              background: '#ffffff',
              boxShadow: '0 0 10px rgba(0,0,0,0.6)',
              transform: 'translateX(-50%)',
              pointerEvents: 'none',
              zIndex: 4,
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: '#d9460f',
                border: '2.5px solid #ffffff',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 900,
                fontSize: 14,
                boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
              }}
            >
              ⇄
            </div>
          </div>

          {/* Input range phủ toàn khung để kéo mượt trên cả chuột, cảm ứng & bàn phím */}
          <input
            type="range"
            min={5}
            max={95}
            value={viTriKeo}
            aria-label={t.sliderAria}
            onChange={(e) => setViTriKeo(Number(e.target.value))}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              opacity: 0,
              cursor: 'ew-resize',
              zIndex: 5,
              margin: 0,
            }}
          />
        </div>
      </div>

      {/* Khối 2: Câu hỏi thường gặp (SEO FAQ) */}
      <div
        style={{
          background: 'var(--nen-the, #ffffff)',
          border: '1.5px solid var(--vien, #e2e8f0)',
          borderRadius: 18,
          padding: '24px 20px',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: 720, margin: '0 auto 18px' }}>
          <h2 style={{ margin: '0 0 6px', fontSize: 21 }}>❓ {t.faqTitle}</h2>
          <p style={{ margin: 0, fontSize: 13.5, color: 'var(--mo, #64748b)' }}>{t.faqSub}</p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: 12,
            maxWidth: 980,
            margin: '0 auto',
          }}
        >
          {t.faqs.map((item, idx) => (
            <details
              key={idx}
              open={idx < 2}
              style={{
                border: '1px solid var(--vien, #e2e8f0)',
                borderRadius: 12,
                padding: '12px 14px',
                background: 'var(--nen-phu, #faf9f6)',
              }}
            >
              <summary
                style={{
                  fontWeight: 700,
                  fontSize: 14,
                  cursor: 'pointer',
                  lineHeight: 1.45,
                }}
              >
                {item.q}
              </summary>
              <p
                style={{
                  margin: '8px 0 0',
                  fontSize: 13.2,
                  lineHeight: 1.6,
                  color: 'var(--mo, #475569)',
                }}
              >
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
