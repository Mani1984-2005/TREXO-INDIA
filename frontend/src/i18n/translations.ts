import type { LanguageCode } from '../types/domain';

interface TranslationDict {
  navDashboard: string;
  navCounter: string;
  navInventory: string;
  navRescue: string;
  navRestock: string;
  navUdhaar: string;
  navReports: string;
  tagline: string;
  cashTrappedLabel: string;
  lostSalesLabel: string;
  todaySalesLabel: string;
  cashRescuedLabel: string;
  rescueAction: string;
  restockAction: string;
  searchPlaceholder: string;
  currentBill: string;
  completeBill: string;
  clearCart: string;
  emptyCartTitle: string;
  emptyCartHint: string;
  deadStockBundleTitle: string;
  addToBill: string;
  localSavedNote: string;
  syncSaving: string;
  syncOffline: string;
  syncSaved: string;
  signOut: string;
  landingEyebrow: string;
  landingHeadlineLine1: string;
  landingHeadlineLine2: string;
  landingHeadlineLine3: string;
  landingSubtitle: string;
  landingSupporting: string;
  landingHighlight1: string;
  landingHighlight2: string;
  landingHighlight3: string;
  landingFooterNote: string;
  loginWelcome: string;
  loginPrompt: string;
  loginPasswordLabel: string;
  loginPasswordPlaceholder: string;
  loginButton: string;
  loginSigningIn: string;
  loginPrivateNote: string;
  loginEmptyError: string;
  loginInvalidError: string;
  loginNetworkError: string;
}

export const TRANSLATIONS: Record<LanguageCode, TranslationDict> = {
  en: {
    navDashboard: 'Dashboard',
    navCounter: 'Counter',
    navInventory: 'Inventory',
    navRescue: 'Rescue Cash',
    navRestock: 'Restock',
    navUdhaar: 'Udhaar',
    navReports: 'Reports',
    tagline: 'Free your cash. Never run out.',
    cashTrappedLabel: 'Cash trapped in dead stock',
    lostSalesLabel: 'Estimated sales lost to stockouts',
    todaySalesLabel: "Today's counter sales",
    cashRescuedLabel: 'Cash rescued from slow stock',
    rescueAction: 'Rescue Stuck Cash',
    restockAction: 'Plan Restock',
    searchPlaceholder: 'Search item name or SKU, press Enter to add...',
    currentBill: 'Current Bill',
    completeBill: 'Complete Bill',
    clearCart: 'Clear',
    emptyCartTitle: 'No items in bill',
    emptyCartHint: 'Tap an item or search and press Enter to start billing.',
    deadStockBundleTitle: 'Counter Dead-Stock Bundle Suggestion',
    addToBill: 'Add',
    localSavedNote: 'Saved on this device',
    syncSaving: 'Saving changes…',
    syncOffline: 'Offline · Saved locally',
    syncSaved: 'Local ledger synced',
    signOut: 'Sign out',
    landingEyebrow: 'YOUR PRIVATE STORE MANAGEMENT SYSTEM',
    landingHeadlineLine1: 'Your Store.',
    landingHeadlineLine2: 'Your Business.',
    landingHeadlineLine3: 'Your Control.',
    landingSubtitle:
      'A smarter way to manage your everyday kirana business. Keep your store organized, your accounts clear, and your business moving forward.',
    landingSupporting:
      'Everything your kirana store needs, thoughtfully brought together in one place.',
    landingHighlight1: 'Smart Store Management',
    landingHighlight2: 'Simple Udhaar Tracking',
    landingHighlight3: 'Everyday Business Insights',
    landingFooterNote: 'Proudly designed for Indian Kirana Stores.',
    loginWelcome: 'Welcome Back!',
    loginPrompt: 'Your store is ready. Sign in to continue.',
    loginPasswordLabel: 'Store Password',
    loginPasswordPlaceholder: 'Enter your store password',
    loginButton: 'Secure Login',
    loginSigningIn: 'Signing in…',
    loginPrivateNote: 'Private access for authorized store owner.',
    loginEmptyError: 'Please enter your store password to continue.',
    loginInvalidError: 'Incorrect store password. Please check and try again.',
    loginNetworkError: 'Could not reach the store sign-in service. Check the connection and try again.',
  },
  hi: {
    navDashboard: 'डैशबोर्ड',
    navCounter: 'काउंटर बिलिंग',
    navInventory: 'स्टॉक खाता',
    navRescue: 'फंसा पैसा निकालें',
    navRestock: 'रीस्टॉक ऑर्डर',
    navUdhaar: 'उधार खाता',
    navReports: 'रिपोर्ट्स',
    tagline: 'फंसा पैसा निकालें। स्टॉक कभी कम न हो।',
    cashTrappedLabel: 'डेड स्टॉक में फंसा पैसा',
    lostSalesLabel: 'स्टॉकआउट से अनुमानित नुकसान',
    todaySalesLabel: 'आज की काउंटर बिक्री',
    cashRescuedLabel: 'स्लो स्टॉक से निकाली गई नकदी',
    rescueAction: 'फंसा पैसा निकालें',
    restockAction: 'रीस्टॉक प्लान करें',
    searchPlaceholder: 'सामान का नाम या SKU खोजें, जोड़ने के लिए Enter दबाएँ...',
    currentBill: 'वर्तमान बिल',
    completeBill: 'बिल पूरा करें',
    clearCart: 'साफ़ करें',
    emptyCartTitle: 'बिल में कोई सामान नहीं',
    emptyCartHint: 'बिल शुरू करने के लिए सामान चुनें या खोजकर Enter दबाएँ।',
    deadStockBundleTitle: 'काउंटर डेड-स्टॉक बंडल सुझाव',
    addToBill: 'जोड़ें',
    localSavedNote: 'इस डिवाइस पर सुरक्षित',
    syncSaving: 'बदलाव सहेजे जा रहे हैं…',
    syncOffline: 'ऑफ़लाइन · डिवाइस पर सुरक्षित',
    syncSaved: 'डिवाइस पर सिंक किया गया',
    signOut: 'लॉग आउट',
    landingEyebrow: 'आपका निजी स्टोर प्रबंधन सिस्टम',
    landingHeadlineLine1: 'आपका स्टोर।',
    landingHeadlineLine2: 'आपका व्यापार।',
    landingHeadlineLine3: 'आपका नियंत्रण।',
    landingSubtitle:
      'अपने रोज़मर्रा के किराना व्यापार को संभालने का समझदार तरीका। अपना स्टॉक व्यवस्थित, खाते साफ़ और व्यापार आगे बढ़ाएँ।',
    landingSupporting: 'आपके किराना स्टोर की हर ज़रूरत, एक ही भरोसेमंद जगह पर।',
    landingHighlight1: 'स्मार्ट स्टोर प्रबंधन',
    landingHighlight2: 'सरल उधार हिसाब',
    landingHighlight3: 'रोज़ाना व्यापार जानकारी',
    landingFooterNote: 'भारतीय किराना स्टोर्स के लिए गर्व से निर्मित।',
    loginWelcome: 'वापसी पर स्वागत है!',
    loginPrompt: 'आपका स्टोर तैयार है। जारी रखने के लिए साइन इन करें।',
    loginPasswordLabel: 'स्टोर पासवर्ड',
    loginPasswordPlaceholder: 'अपना स्टोर पासवर्ड दर्ज करें',
    loginButton: 'सुरक्षित लॉगिन',
    loginSigningIn: 'साइन इन हो रहा है…',
    loginPrivateNote: 'केवल अधिकृत स्टोर मालिक के लिए निजी पहुँच।',
    loginEmptyError: 'कृपया जारी रखने के लिए अपना स्टोर पासवर्ड दर्ज करें।',
    loginInvalidError: 'गलत स्टोर पासवर्ड। कृपया जाँच कर पुनः प्रयास करें।',
    loginNetworkError: 'स्टोर साइन-इन सेवा से संपर्क नहीं हो पाया। कनेक्शन जाँचकर फिर प्रयास करें।',
  },
  kn: {
    navDashboard: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
    navCounter: 'ಕೌಂಟರ್ ಬಿಲ್ಲಿಂಗ್',
    navInventory: 'ಸ್ಟಾಕ್ ವಿವರ',
    navRescue: 'ಹಣ ಬಿಡುಗಡೆ',
    navRestock: 'ರೀಸ್ಟಾಕ್',
    navUdhaar: 'ಉಧಾರ್ ಖಾತೆ',
    navReports: 'ವರದಿಗಳು',
    tagline: 'ಸಿಲುಕಿದ ಹಣ ಬಿಡುಗಡೆ ಮಾಡಿ. ಸ್ಟಾಕ್ ಮುಗಿಯದಿರಲಿ.',
    cashTrappedLabel: 'ಡೆಡ್ ಸ್ಟಾಕ್‌ನಲ್ಲಿ ಸಿಲುಕಿದ ಹಣ',
    lostSalesLabel: 'ಸ್ಟಾಕ್ ಇಲ್ಲದೆ ಅಂದಾಜು ನಷ್ಟ',
    todaySalesLabel: 'ಇಂದಿನ ಕೌಂಟರ್ ಮಾರಾಟ',
    cashRescuedLabel: 'ಬಿಡುಗಡೆಯಾದ ನಗದು',
    rescueAction: 'ಹಣ ಬಿಡುಗಡೆ ಮಾಡಿ',
    restockAction: 'ರೀಸ್ಟಾಕ್ ಯೋಜಿಸಿ',
    searchPlaceholder: 'ವಸ್ತುವಿನ ಹೆಸರು ಅಥವಾ SKU ಹುಡುಕಿ, ಸೇರಿಸಲು Enter ಒತ್ತಿ...',
    currentBill: 'ಪ್ರಸ್ತುತ ಬಿಲ್',
    completeBill: 'ಬಿಲ್ ಪೂರ್ಣಗೊಳಿಸಿ',
    clearCart: 'ತೆರವುಗೊಳಿಸಿ',
    emptyCartTitle: 'ಬಿಲ್‌ನಲ್ಲಿ ಯಾವುದೇ ವಸ್ತುಗಳಿಲ್ಲ',
    emptyCartHint: 'ಬಿಲ್ಲಿಂಗ್ ಪ್ರಾರಂಭಿಸಲು ವಸ್ತುವನ್ನು ಟ್ಯಾಪ್ ಮಾಡಿ ಅಥವಾ ಹುಡುಕಿ.',
    deadStockBundleTitle: 'ಕೌಂಟರ್ ಡೆಡ್-ಸ್ಟಾಕ್ ಬಂಡಲ್ ಸಲಹೆ',
    addToBill: 'ಸೇರಿಸಿ',
    localSavedNote: 'ಈ ಸಾಧನದಲ್ಲಿ ಉಳಿಸಲಾಗಿದೆ',
    syncSaving: 'ಉಳಿಸಲಾಗುತ್ತಿದೆ…',
    syncOffline: 'ಆಫ್‌ಲೈನ್ · ಸಾಧನದಲ್ಲಿ ಉಳಿಸಲಾಗಿದೆ',
    syncSaved: 'ಸ್ಥಳೀಯವಾಗಿ ಸಿಂಕ್ ಆಗಿದೆ',
    signOut: 'ಸೈನ್ ಔಟ್',
    landingEyebrow: 'ನಿಮ್ಮ ಖಾಸಗಿ ಅಂಗಡಿ ನಿರ್ವಹಣಾ ವ್ಯವಸ್ಥೆ',
    landingHeadlineLine1: 'ನಿಮ್ಮ ಅಂಗಡಿ.',
    landingHeadlineLine2: 'ನಿಮ್ಮ ವ್ಯಾಪಾರ.',
    landingHeadlineLine3: 'ನಿಮ್ಮ ನಿಯಂತ್ರಣ.',
    landingSubtitle:
      'ನಿಮ್ಮ ದೈನಂದಿನ ಕಿರಾಣಿ ವ್ಯಾಪಾರವನ್ನು ನಿರ್ವಹಿಸಲು ಸ್ಮಾರ್ಟ್ ಮಾರ್ಗ. ಅಂಗಡಿ ವ್ಯವಸ್ಥಿತವಾಗಿರಲಿ, ಲೆಕ್ಕಪತ್ರ ಸ್ಪಷ್ಟವಾಗಿರಲಿ.',
    landingSupporting: 'ನಿಮ್ಮ ಕಿರಾಣಿ ಅಂಗಡಿಗೆ ಬೇಕಾದ ಎಲ್ಲವೂ ಒಂದೇ ವಿಶ್ವಾಸಾರ್ಹ ಸ್ಥಳದಲ್ಲಿ.',
    landingHighlight1: 'ಸ್ಮಾರ್ಟ್ ಅಂಗಡಿ ನಿರ್ವಹಣೆ',
    landingHighlight2: 'ಸರಳ ಉಧಾರ್ ಟ್ರ್ಯಾಕಿಂಗ್',
    landingHighlight3: 'ದೈನಂದಿನ ವ್ಯಾಪಾರ ಒಳನೋಟಗಳು',
    landingFooterNote: 'ಭಾರತೀಯ ಕಿರಾಣಿ ಅಂಗಡಿಗಳಿಗಾಗಿ ಹೆಮ್ಮೆಯಿಂದ ವಿನ್ಯಾಸಗೊಳಿಸಲಾಗಿದೆ.',
    loginWelcome: 'ಮರಳಿ ಸ್ವಾಗತ!',
    loginPrompt: 'ನಿಮ್ಮ ಅಂಗಡಿ ಸಿದ್ಧವಾಗಿದೆ. ಮುಂದುವರಿಯಲು ಸೈನ್ ಇನ್ ಮಾಡಿ.',
    loginPasswordLabel: 'ಅಂಗಡಿ ಪಾಸ್‌ವರ್ಡ್',
    loginPasswordPlaceholder: 'ನಿಮ್ಮ ಅಂಗಡಿ ಪಾಸ್‌ವರ್ಡ್ ನಮೂದಿಸಿ',
    loginButton: 'ಸುರಕ್ಷಿತ ಲಾಗಿನ್',
    loginSigningIn: 'ಸೈನ್ ಇನ್ ಆಗುತ್ತಿದೆ…',
    loginPrivateNote: 'ಅಧಿಕೃತ ಅಂಗಡಿ ಮಾಲೀಕರಿಗೆ ಮಾತ್ರ ಖಾಸಗಿ ಪ್ರವೇಶ.',
    loginEmptyError: 'ಮುಂದುವರಿಯಲು ದಯವಿಟ್ಟು ನಿಮ್ಮ ಅಂಗಡಿ ಪಾಸ್‌ವರ್ಡ್ ನಮೂದಿಸಿ.',
    loginInvalidError: 'ತಪ್ಪಾದ ಅಂಗಡಿ ಪಾಸ್‌ವರ್ಡ್. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    loginNetworkError: 'ಅಂಗಡಿ ಸೈನ್-ಇನ್ ಸೇವೆಯನ್ನು ಸಂಪರ್ಕಿಸಲಾಗಲಿಲ್ಲ. ಸಂಪರ್ಕ ಪರಿಶೀಲಿಸಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
  },
};
