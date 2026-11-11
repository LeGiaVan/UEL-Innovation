import {
  GraduationCap,
  Brain,
  Calculator,
  HelpCircle,
  CalendarDays,
  Mail,
  Layers,
} from 'lucide-react'

/**
 * Đặc trưng từng tính năng: màu, icon, copy — đồng bộ sidebar / header / vùng chat.
 */
export const FEATURE_DEFS = [
  {
    key: 'ctdt',
    slug: 'chuong-trinh-dao-tao',
    moduleId: 'module_1_1',
    label: 'Chương trình đào tạo',
    bot_name: 'Ngành, đại học, thạc sĩ, tiến sĩ',
    title: 'Chương trình đào tạo',
    tagline:
      'Ngành, bậc đại học, thạc sĩ, tiến sĩ — chỉ tiêu và thông tin chương trình theo quy định tuyển sinh UEL.',
    accent: '#144E8C',
    accentSoft: 'rgba(20, 78, 140, 0.14)',
    Icon: GraduationCap,
    welcome: {
      headline: 'Chương trình đào tạo',
      intro:
        'Trợ lý giải đáp về ngành, bậc đại học / thạc sĩ / tiến sĩ, chỉ tiêu, mã và phương thức xét tuyển theo thông báo chính thức của UEL. Thích hợp khi bạn so sánh ngành, nắm cấu trúc chương trình hoặc tra cứu theo từng bậc.',
      bulletsTitle: 'Gợi ý câu hỏi',
      bullets: [
        'Ngành X tuyển bao nhiêu chỉ tiêu năm 2026? Điều kiện xét tuyển là gì?',
        'Chương trình đại học chính quy có những ngành / nhóm ngành nào?',
        'Thạc sĩ / tiến sĩ có những chương trình và hình thức đào tạo nào?',
        'Mã ngành / tổ hợp môn xét tuyển của ngành em quan tâm là gì?',
      ],
      footerHint:
        'Nhập câu hỏi cụ thể về ngành hoặc bậc đào tạo.',
    },
  },
  {
    key: 'holland',
    slug: 'holland-mbti',
    moduleId: 'module_2',
    label: 'Trắc nghiệm Holland & MBTI',
    bot_name: 'Trắc nghiệm Holland & MBTI',
    title: 'Trắc nghiệm Holland & MBTI',
    tagline:
      'Khám phá sở thích nghề nghiệp và nhóm tính cách qua nội dung Holland và MBTI do UEL công bố.',
    accent: '#5E35B1',
    accentSoft: 'rgba(94, 53, 177, 0.14)',
    Icon: Brain,
    welcome: {
      headline: 'Trắc nghiệm Holland & MBTI',
      intro:
        'Trợ lý hướng dẫn nội dung Holland (RIASEC), MBTI và các hoạt động định hướng tương ứng — giúp bạn hiểu khung sở thích nghề nghiệp và tham khảo (không thay thế tư vấn tâm lý chuyên sâu hay chẩn đoán).',
      bulletsTitle: 'Gợi ý câu hỏi',
      bullets: [
        'Holland có mấy nhóm sở thích (RIASEC)? Ý nghĩa từng nhóm là gì?',
        'MBTI gồm những cặp đặc điểm nào? Cách đọc kết quả tổng quan?',
        'Phần định hướng có hướng dẫn làm bài / chấm điểm thế nào?',
        'Nếu em thiên về nhóm R/I/A thì có thể tham khảo hướng ngành nào?',
      ],
      footerHint:
        'Hãy nói rõ bạn muốn hiểu về Holland, MBTI hay cách ứng dụng kết quả trong bối cảnh tuyển sinh.',
    },
  },
  {
    key: 'diem',
    slug: 'tham-so-xet-tuyen',
    moduleId: 'module_3',
    label: 'Tham số tính điểm xét tuyển',
    bot_name: 'Điểm xét tuyển',
    title: 'Tham số & tính điểm',
    tagline:
      'Công thức, hệ số, đối tượng xét tuyển và gợi ý nhập liệu theo quy định năm 2026.',
    accent: '#E65100',
    accentSoft: 'rgba(230, 81, 0, 0.14)',
    Icon: Calculator,
    welcome: {
      headline: 'Điểm xét tuyển',
      intro:
        'Trợ lý giải thích tham số, công thức, đối tượng (ĐT), điểm học lực, điểm thi và các hệ số theo quy định xét tuyển. Nếu bạn đã nhập đủ số liệu vào phần tính thử, phần giải thích sẽ thống nhất với kết quả đó.',
      bulletsTitle: 'Gợi ý câu hỏi',
      bullets: [
        'ĐT1 / ĐT2 / ĐT3 / ĐT4 khác nhau thế nào về cách tính điểm học lực?',
        'Công thức điểm xét tuyển thang 100 gồm những thành phần nào?',
        'Điểm cộng chứng chỉ tiếng Anh (IELTS, TOEIC, …) quy định ra sao?',
        'Em có điểm THPT …, học lực …, có được cộng … — em thuộc đối tượng nào?',
      ],
      footerHint:
        'Có thể gửi một đoạn liệt kê điểm và nguyện vọng; trợ lý sẽ giải thích tham số hoặc gợi ý cách nhập cho phần tính thử.',
    },
  },
  {
    key: 'faq',
    slug: 'faq',
    moduleId: 'module_1_2',
    label: 'FAQ',
    bot_name: 'FAQ',
    title: 'Hỏi đáp nhanh',
    tagline: 'Câu hỏi thường gặp về tuyển sinh, nhập học và liên hệ các đơn vị.',
    accent: '#2E7D32',
    accentSoft: 'rgba(46, 125, 50, 0.14)',
    Icon: HelpCircle,
    welcome: {
      headline: 'FAQ',
      intro:
        'Trợ lý trả lời các câu hỏi thường gặp về tuyển sinh, nhập học, học phí, hồ sơ và liên hệ đơn vị — ngắn gọn, đúng trọng tâm.',
      bulletsTitle: 'Gợi ý câu hỏi',
      bullets: [
        'Điều kiện nhập học và thời hạn nộp hồ sơ cần lưu ý gì?',
        'Liên hệ Phòng Tuyển sinh và Công tác sinh viên hoặc khoa để hỏi thêm thì sao?',
        'Có những câu hỏi thường gặp nào về học bổng / ký túc xá / chương trình song ngữ?',
        'Có hướng dẫn về đăng ký trực tuyến hoặc xác nhận nhập học không?',
      ],
      footerHint:
        'Đặt câu hỏi đúng từ khóa (ví dụ “học phí”, “hồ sơ”, “hotline”).',
    },
  },
  {
    key: 'lich',
    slug: 'moc-thoi-gian',
    moduleId: 'module_1_3',
    label: 'Mốc thời gian tuyển sinh',
    bot_name: 'Lịch tuyển sinh',
    title: 'Mốc thời gian',
    tagline: 'Lịch đăng ký, xét tuyển, nhập học và các hạn chót quan trọng trong năm.',
    accent: '#0277BD',
    accentSoft: 'rgba(2, 119, 189, 0.14)',
    Icon: CalendarDays,
    welcome: {
      headline: 'Lịch tuyển sinh',
      intro:
        'Trợ lý tổng hợp các ngày, hạn và lịch theo thông báo tuyển sinh năm 2026, ưu tiên độ chính xác thời gian và từng đợt xét tuyển / nhập học.',
      bulletsTitle: 'Gợi ý câu hỏi',
      bullets: [
        'Hạn đăng ký / nộp hồ sơ / xác nhận nhập học theo tài liệu năm 2026 là khi nào?',
        'Các mốc thi, công bố kết quả hoặc làm thủ tục nhập học được ghi như thế nào?',
        'Có lưu ý riêng theo đợt xét tuyển hay theo phương thức không?',
        'Hạn chót nào liên quan đến nộp bản cứng / xác nhận trực tuyến?',
      ],
      footerHint:
        'Hỏi theo sự kiện (“khi nào nộp hồ sơ”, “hạn xác nhận”).',
    },
  },
  {
    key: 'bskt',
    slug: 'bo-sung-kien-thuc',
    moduleId: 'module_7',
    label: 'Bổ sung kiến thức (Sau đại học)',
    bot_name: 'Bổ sung kiến thức Thạc sĩ – Tiến sĩ',
    title: 'Bổ sung kiến thức',
    tagline:
      'Tra cứu: tốt nghiệp ngành nào được miễn hay phải học bổ sung kiến thức khi dự tuyển Thạc sĩ / Tiến sĩ.',
    accent: '#00695C',
    accentSoft: 'rgba(0, 105, 92, 0.14)',
    Icon: Layers,
    welcome: {
      headline: 'Bổ sung kiến thức (Sau đại học)',
      intro:
        'Trợ lý tra cứu danh mục bổ sung kiến thức khi dự tuyển Thạc sĩ / Tiến sĩ tại UEL: tốt nghiệp ngành nào được miễn, ngành nào phải học bổ sung và gồm những môn gì. Hãy nêu rõ BẬC dự tuyển, NGÀNH dự tuyển và NGÀNH bạn đã tốt nghiệp.',
      bulletsTitle: 'Gợi ý câu hỏi',
      bullets: [
        'Tốt nghiệp cử nhân Quản trị kinh doanh, dự tuyển Thạc sĩ Tài chính – Ngân hàng có phải học bổ sung không?',
        'Cử nhân Kinh tế học lên Thạc sĩ Kinh tế quốc tế có cần bổ sung kiến thức không?',
        'Thạc sĩ Luật kinh tế dự tuyển Tiến sĩ Luật Kinh tế thì sao?',
        'Dự tuyển Tiến sĩ Tài chính – Ngân hàng phải học bổ sung những môn nào?',
      ],
      footerHint:
        'Nêu rõ ngành đã tốt nghiệp + bậc/ngành muốn dự tuyển để được tra cứu chính xác.',
    },
  },
]

export const REGISTRATION_FEATURE = {
  key: 'dangky',
  path: '/dang-ky-nhan-tin',
  moduleId: 'module_6',
  label: 'Đăng ký nhận tư vấn tuyển sinh chuyên sâu',
  bot_name: 'Tư vấn tuyển sinh chuyên sâu',
  title: 'Đăng ký nhận tư vấn tuyển sinh chuyên sâu',
  tagline:
    'Để lại thông tin để Phòng Tuyển sinh và Công tác sinh viên gửi cập nhật tuyển sinh hoặc liên hệ hỗ trợ.',
  accent: '#E65100',
  accentDeep: '#BF360C',
  accentSoft: 'rgba(230, 81, 0, 0.14)',
  Icon: Mail,
  kind: 'registration',
}

/** Hub admission gọi trực tiếp module_1 (CTĐT + FAQ + lịch tuyển sinh đã gộp về 1 module). */
export const ADMISSION_INFO_SLUG = 'thong-tin-tuyen-sinh'

const ADMISSION_HUB_PATH_SLUGS = new Set([
  ADMISSION_INFO_SLUG,
  'chuong-trinh-dao-tao',
  'faq',
  'moc-thoi-gian',
])

/**
 * 3 thẻ gợi ý nội dung — tất cả cùng route, không bắt chọn 1.1/1.2/1.3
 */
export const ADMISSION_PANEL_CARDS = [
  {
    key: 'ctdt',
    targetSlug: ADMISSION_INFO_SLUG,
    moduleId: 'module_1',
    title: 'Chương trình đào tạo',
    body:
      'Giải đáp về ngành, bậc đại học / thạc sĩ / tiến sĩ, chỉ tiêu, mã và phương thức xét tuyển theo thông báo chính thức của UEL',
    iconImage: 'image_module_1_1.png',
  },
  {
    key: 'faq',
    targetSlug: ADMISSION_INFO_SLUG,
    moduleId: 'module_1',
    title: 'FAQ',
    body:
      'Trả lời các câu hỏi thường gặp về tuyển sinh, nhập học, học phí, hồ sơ và liên hệ đơn vị',
    iconImage: 'image_module_1_2.png',
  },
  {
    key: 'lich',
    targetSlug: ADMISSION_INFO_SLUG,
    moduleId: 'module_1',
    title: 'Lịch tuyển sinh',
    body: 'Tổng hợp các ngày, hạn và lịch theo thông báo tuyển sinh năm 2026',
    iconImage: 'image_module_1_3.png',
  },
]

export const ADMISSION_HUB_FEATURE = {
  key: 'admission',
  kind: 'admission_hub',
  slug: ADMISSION_INFO_SLUG,
  label: 'Thông tin tuyển sinh',
  title: 'Thông tin tuyển sinh',
  moduleId: 'module_1',
  accent: '#144E8C',
  accentSoft: 'rgba(20, 78, 140, 0.14)',
  Icon: GraduationCap,
  admission: true,
}

/** Màn chào chung — không còn gắn 1.1/1.2/1.3; tất cả route về module_1 (CTĐT + FAQ + lịch). */
export const ADMISSION_HUB_WELCOME = {
  headline: 'Thông tin tuyển sinh',
  intro:
    'Bạn hỏi tự nhiên — hệ thống tự chọn tài liệu phù hợp: chương trình & ngành (1.1), hỏi đáp thường gặp (1.2) hoặc mốc thời gian tuyển sinh (1.3) để trả lời.',
  bulletsTitle: 'Gợi ý câu hỏi',
  bullets: [
    'Học phí, hồ sơ, cách liên hệ Phòng Tuyển sinh và Công tác sinh viên thế nào?',
    'Các mốc đăng ký, hạn nộp, lịch thi ĐGNL, xác nhận nhập học theo từng đợt ra sao?',
    'Thạc sĩ / tiến sĩ có chương trình nào và điều kiện đầu vào từng bậc?',
  ],
  footerHint: 'Không cần bấm chọn 1.1 / 1.2 / 1.3 — hãy gõ đúng câu hỏi; kết quả hiển thị loại tài liệu đang dùng ở nhãn tin nhắn.',
}

/**
 * Có phải route /bot/… thuộc nhóm Thông tin tuyển sinh (hub + 2 slug cũ) không
 */
export function isAdmissionHubPathname(pathname) {
  if (!pathname) return false
  const m = pathname.match(/^\/bot\/([^/?#]+)/)
  const s = m?.[1]
  return Boolean(s && ADMISSION_HUB_PATH_SLUGS.has(s))
}

/**
 * Bảng điều khiển trái: 4 mục (gộp CTĐT + FAQ + lịch vào «Thông tin tuyển sinh»).
 */
export const SIDEBAR_NAV_ITEMS = [
  {
    key: 'admission',
    to: `/bot/${ADMISSION_INFO_SLUG}`,
    isActive: (pathname) => {
      const m = pathname.match(/^\/bot\/([^/?#]+)(\/|$)/)
      return Boolean(m?.[1] && ADMISSION_HUB_PATH_SLUGS.has(m[1]))
    },
    label: 'Thông tin tuyển sinh',
    sub: 'Chương trình đào tạo, FAQ, lịch tuyển sinh',
    Icon: GraduationCap,
    iconImage: 'image_module_1.png',
  },
  {
    key: 'personality',
    to: '/bot/holland-mbti',
    isActive: (pathname) => /^\/bot\/holland-mbti(\/|$)/.test(pathname),
    label: 'Khám phá tính cách',
    sub: 'Trắc nghiệm Holland & MBTI',
    Icon: Brain,
    iconImage: 'image_module_2.png',
  },
  {
    key: 'scoring',
    to: '/bot/tham-so-xet-tuyen',
    isActive: (pathname) => /^\/bot\/tham-so-xet-tuyen(\/|$)/.test(pathname),
    label: 'Tính điểm xét tuyển',
    sub: 'Đại học chính quy',
    Icon: Calculator,
    iconImage: 'image_module_3.png',
  },
  {
    key: 'bskt',
    to: '/bot/bo-sung-kien-thuc',
    isActive: (pathname) => /^\/bot\/bo-sung-kien-thuc(\/|$)/.test(pathname),
    label: 'Bổ sung kiến thức',
    sub: 'Sau đại học',
    Icon: Layers,
  },
  {
    key: 'registration',
    to: REGISTRATION_FEATURE.path,
    isActive: (pathname) =>
      pathname === REGISTRATION_FEATURE.path || pathname.startsWith(`${REGISTRATION_FEATURE.path}/`),
    label: 'Đăng ký nhận tư vấn',
    sub: REGISTRATION_FEATURE.bot_name,
    Icon: Mail,
    /** Ảnh sidebar — trang đăng ký không dùng icon trong tiêu đề (xem RegistrationPage) */
    iconImage: 'image_module_4.png',
  },
]

export const DEFAULT_BOT_PATH = `/bot/${ADMISSION_INFO_SLUG}`

/** Tên hiển thị khi API modes chưa tải — tránh hiện raw `module_1`. */
const MODULE_ID_DISPLAY_FALLBACK = {
  auto: 'Tự động theo câu hỏi',
  module_1_1: '1.1 Chương trình đào tạo',
  module_1_2: '1.2 FAQ',
  module_1_3: '1.3 Lịch tuyển sinh',
  module_1: '1.1 Chương trình đào tạo', // alias tương thích
  module_2: 'Trắc nghiệm Holland & MBTI',
  module_3: 'Điểm xét tuyển',
  module_4: '1.2 FAQ',
  module_5: '1.3 Lịch tuyển sinh',
  module_6: 'Tư vấn tuyển sinh chuyên sâu',
}

/**
 * Tên bot ngắn cho badge (resolved_mode): ưu tiên API → feature → map cố định.
 * @param {string} moduleId
 * @param {Array<{id:string,bot_name?:string,label?:string}>} modesFromApi
 */
export function displayNameForResolvedMode(moduleId, modesFromApi = []) {
  if (!moduleId) return ''
  const row = modesFromApi.find((x) => x.id === moduleId)
  if (row?.bot_name) return row.bot_name
  if (row?.label) return row.label
  const feat = FEATURE_DEFS.find((f) => f.moduleId === moduleId)
  if (feat?.bot_name) return feat.bot_name
  if (REGISTRATION_FEATURE.moduleId === moduleId) return REGISTRATION_FEATURE.bot_name
  return MODULE_ID_DISPLAY_FALLBACK[moduleId] || moduleId
}

/** Giữ tương thích import cũ */
export const BOT_CHAT_NAV = FEATURE_DEFS.map(
  ({ slug, moduleId, label, bot_name }) => ({ slug, moduleId, label, bot_name })
)

export const REGISTRATION = {
  path: REGISTRATION_FEATURE.path,
  label: REGISTRATION_FEATURE.label,
  bot_name: REGISTRATION_FEATURE.bot_name,
}

const _slugToModule = {
  ...Object.fromEntries(FEATURE_DEFS.map((f) => [f.slug, f.moduleId])),
  [ADMISSION_INFO_SLUG]: 'module_1',
  'chuong-trinh-dao-tao': 'module_1',
  faq: 'module_1',
  'moc-thoi-gian': 'module_1',
}

export function getModuleIdBySlug(slug) {
  if (!slug || typeof slug !== 'string') return undefined
  return _slugToModule[slug]
}

/** Nội dung màn hình chào trong chat — khu vực admission: một bộ gợi ý (bot dùng mode `auto` trên API). */
export function getChatWelcome(feature) {
  if (feature?.admission) {
    return ADMISSION_HUB_WELCOME
  }
  if (feature?.welcome) return feature.welcome
  return FEATURE_DEFS[0].welcome
}

export function resolveFeatureFromPathname(pathname) {
  if (!pathname) return { ...ADMISSION_HUB_FEATURE, moduleId: 'module_1' }
  if (pathname === REGISTRATION_FEATURE.path || pathname.startsWith(`${REGISTRATION_FEATURE.path}/`)) {
    return REGISTRATION_FEATURE
  }
  const m = pathname.match(/^\/bot\/([^/?#]+)/)
  const slug = m?.[1]
  if (slug && ADMISSION_HUB_PATH_SLUGS.has(slug)) {
    const mod = getModuleIdBySlug(slug) || 'module_1'
    return { ...ADMISSION_HUB_FEATURE, moduleId: mod, slug, title: 'Thông tin tuyển sinh' }
  }
  const found = FEATURE_DEFS.find((f) => f.slug === slug)
  if (found) return found
  return { ...ADMISSION_HUB_FEATURE, moduleId: 'module_1' }
}

export function featureCssVars(feature) {
  if (!feature) return {}
  return {
    '--feature-accent': feature.accent,
    '--feature-accent-soft': feature.accentSoft,
  }
}
