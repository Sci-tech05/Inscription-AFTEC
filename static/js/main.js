(function () {
    if (window.AOS) {
        AOS.init({ duration: 800, once: true });
    }

    const THEME_STORAGE_KEY = 'aftec2026_theme';
    const themeToggle = document.getElementById('themeToggle');

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        if (!themeToggle) return;
        const isDark = theme === 'dark';
        themeToggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
        const label = isDark ? 'Activer le mode clair' : 'Activer le mode sombre';
        themeToggle.setAttribute('aria-label', label);
        themeToggle.setAttribute('title', label);
    }

    function initTheme() {
        const stored = localStorage.getItem(THEME_STORAGE_KEY);
        const theme = stored === 'dark' ? 'dark' : 'light';
        applyTheme(theme);
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            localStorage.setItem(THEME_STORAGE_KEY, next);
            applyTheme(next);
        });
    }

    initTheme();

    document.querySelectorAll('.counter').forEach((counter) => {
        const target = parseInt(counter.dataset.target || '0', 10);
        let value = 0;
        const step = Math.max(1, Math.ceil(target / 40));
        const timer = setInterval(() => {
            value += step;
            if (value >= target) {
                value = target;
                clearInterval(timer);
            }
            counter.textContent = value;
        }, 25);
    });

    const form = document.getElementById('inscriptionForm');
    if (!form) return;

    const panes = Array.from(document.querySelectorAll('.step-pane'));
    const prevBtn = document.getElementById('prevStep');
    const nextBtn = document.getElementById('nextStep');
    const submitBtn = document.getElementById('submitBtn');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const currentStepLabel = document.getElementById('currentStepLabel');
    const eligibilityBanner = document.getElementById('eligibilityBanner');
    const minorAlert = document.getElementById('minorAlert');
    const parentConsentWrap = document.getElementById('parentConsentWrap');
    const autorisationBlock = document.getElementById('autorisationBlock');
    const communeWarning = document.getElementById('communeWarning');
    const classeNiveauInput = document.getElementById('id_classe_niveau');
    const higherLevelHint = document.getElementById('higherLevelHint');
    const academicGeneralBlocks = Array.from(document.querySelectorAll('.academic-general'));
    const optionalMathPhysicsBlocks = Array.from(document.querySelectorAll('.optional-math-physics'));
    const professionalBlocks = Array.from(document.querySelectorAll('.professional-only'));
    const professionalBulletinBlocks = Array.from(document.querySelectorAll('.professional-bulletin'));
    const diplomeSelect = document.getElementById('id_diplome_plus_eleve');
    const attestationDiplomeInput = document.getElementById('id_attestation_diplome');
    const dernierReleveInput = document.getElementById('id_dernier_releve_notes');
    const bulletinAn1Input = document.getElementById('id_bulletin_an1');
    const bulletinAn2Input = document.getElementById('id_bulletin_an2');
    const quizPane = document.querySelector('.step-pane[data-step="6"]');
    const quizTabButtons = Array.from(document.querySelectorAll('#quizTabs button[data-bs-target]'));
    const timerEl = document.getElementById('quizTimer');

    const STORAGE_KEY = 'aftec2026_form';
    const HIGHER_LEVELS = new Set(['L1', 'L2', 'L3', 'M1', 'M2']);
    const PROFESSIONAL_LEVEL = 'AUTRE';
    let currentStep = 1;
    let quizTimerSeconds = 0;
    let quizTimerInterval = null;

    function isHigherLevel() {
        return HIGHER_LEVELS.has((classeNiveauInput?.value || '').trim());
    }

    function isProfessionalLevel() {
        return (classeNiveauInput?.value || '').trim() === PROFESSIONAL_LEVEL;
    }

    function updateAcademicFieldsByLevel() {
        const isProfessional = isProfessionalLevel();
        const higherLevel = isHigherLevel();

        academicGeneralBlocks.forEach((block) => {
            block.classList.toggle('d-none', isProfessional);
            const input = block.querySelector('input');
            if (!input) return;
            input.required = !isProfessional;
            input.disabled = isProfessional;
            if (isProfessional) {
                input.value = '';
            }
        });

        optionalMathPhysicsBlocks.forEach((block) => {
            const hideField = isProfessional || higherLevel;
            block.classList.toggle('d-none', hideField);
            const input = block.querySelector('input');
            if (!input) return;
            input.required = !hideField;
            input.disabled = hideField;
            if (hideField) {
                input.value = '';
            }
        });

        professionalBlocks.forEach((block) => {
            block.classList.toggle('d-none', !isProfessional);
            block.querySelectorAll('input, select').forEach((input) => {
                input.disabled = !isProfessional;
            });
        });

        if (diplomeSelect) {
            diplomeSelect.required = isProfessional;
        }
        if (attestationDiplomeInput) {
            attestationDiplomeInput.required = isProfessional;
        }
        if (dernierReleveInput) {
            dernierReleveInput.required = isProfessional;
        }

        professionalBulletinBlocks.forEach((block) => {
            block.classList.toggle('d-none', isProfessional);
        });
        if (bulletinAn1Input) {
            bulletinAn1Input.required = !isProfessional;
            bulletinAn1Input.disabled = isProfessional;
        }
        if (bulletinAn2Input) {
            bulletinAn2Input.required = !isProfessional;
            bulletinAn2Input.disabled = isProfessional;
        }

        if (higherLevelHint) {
            higherLevelHint.classList.toggle('d-none', !higherLevel || isProfessional);
        }
    }

    function saveDraft() {
        const data = {};
        Array.from(form.elements).forEach((el) => {
            if (!el.name || el.type === 'file' || el.disabled) return;
            if (el.type === 'checkbox' || el.type === 'radio') {
                data[el.name] = el.checked || (el.type === 'radio' && el.checked ? el.value : data[el.name]);
            } else {
                data[el.name] = el.value;
            }
        });
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }

    function restoreDraft() {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        try {
            const data = JSON.parse(raw);
            Object.entries(data).forEach(([name, value]) => {
                const elements = form.querySelectorAll(`[name="${name}"]`);
                if (!elements.length) return;
                elements.forEach((el) => {
                    if (el.type === 'checkbox') {
                        el.checked = Boolean(value);
                    } else if (el.type === 'radio') {
                        el.checked = el.value === value;
                    } else if (typeof value === 'string') {
                        el.value = value;
                    }
                });
            });
        } catch (error) {
            console.warn('Draft restore failed', error);
        }
    }

    function calculateAge() {
        const birthInput = document.getElementById('id_date_naissance');
        if (!birthInput || !birthInput.value) return null;
        const dob = new Date(birthInput.value);
        const today = new Date();
        let age = today.getFullYear() - dob.getFullYear();
        const m = today.getMonth() - dob.getMonth();
        if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
            age -= 1;
        }
        return age;
    }

    function updateEligibilityIndicators() {
        const age = calculateAge();
        const commune = (document.getElementById('id_commune_residence')?.value || '').toLowerCase();

        const isMinor = age !== null && age < 18;
        const isTooYoung = age !== null && age < 14;

        if (isTooYoung) {
            eligibilityBanner.classList.remove('d-none');
            eligibilityBanner.textContent = 'Inéligible: âge inférieur à 14 ans (critère impératif AFTEC 2026).';
        } else {
            eligibilityBanner.classList.add('d-none');
            eligibilityBanner.textContent = '';
        }

        if (isMinor) {
            minorAlert.classList.remove('d-none');
            parentConsentWrap.classList.remove('d-none');
            autorisationBlock.classList.remove('d-none');
        } else {
            minorAlert.classList.add('d-none');
            parentConsentWrap.classList.add('d-none');
            autorisationBlock.classList.add('d-none');
            const parentConsent = document.getElementById('id_consent_autorisation_parentale_declaree');
            if (parentConsent) parentConsent.checked = false;
        }

        const inArea = /(pob|kétou|ketou|adja|issaba|sakete|sakété|plateau)/.test(commune);
        if (!inArea && commune.trim()) {
            communeWarning.classList.remove('d-none');
            communeWarning.textContent = 'Avertissement : commune hors Pobè/environs détectée. Candidature possible, priorité locale éventuelle.';
        } else {
            communeWarning.classList.add('d-none');
        }
    }

    function updateScoreMeters() {
        document.querySelectorAll('.score-field input').forEach((input) => {
            if (input.disabled) return;
            const meter = input.parentElement.querySelector('.score-meter');
            if (!meter) return;
            const value = parseFloat(input.value || '0');
            const pct = Math.min(100, Math.max(0, (value / 20) * 100));
            let color = '#E94560';
            if (value >= 12) color = '#0F9B58';
            else if (value >= 10) color = '#F5A623';
            meter.style.setProperty('--score-width', `${pct}%`);
            meter.style.setProperty('--score-color', color);
        });
    }

    function updateDocumentBadges() {
        document.querySelectorAll('.document-field').forEach((block) => {
            const input = block.querySelector('input[type="file"]');
            const badge = block.querySelector('.doc-badge');
            const preview = block.querySelector('.doc-preview');
            if (!input || !badge) return;
            if (input.files && input.files.length > 0) {
                const file = input.files[0];
                badge.textContent = 'Fichier ajouté';
                badge.classList.add('ok');
                badge.classList.remove('missing');
                if (preview) {
                    preview.innerHTML = '';
                    const mime = (file.type || '').toLowerCase();
                    if (mime.startsWith('image/')) {
                        const img = document.createElement('img');
                        img.src = URL.createObjectURL(file);
                        img.alt = 'Aperçu';
                        preview.appendChild(img);
                    } else {
                        preview.textContent = file.name;
                    }
                }
            } else {
                badge.textContent = 'Manquant';
                badge.classList.add('missing');
                badge.classList.remove('ok');
                if (preview) {
                    preview.textContent = '';
                }
            }
        });
    }

    function validateStep(step) {
        const pane = panes.find((p) => parseInt(p.dataset.step, 10) === step);
        if (!pane) return true;

        if (step === 1) {
            const required = [
                'id_consent_donnees_personnelles',
                'id_consent_selection',
                'id_consent_reglement',
                'id_consent_photos_videos',
                'id_consent_engagement_presence',
            ];
            for (const id of required) {
                const el = document.getElementById(id);
                if (el && !el.checked) return false;
            }
            if (!parentConsentWrap.classList.contains('d-none')) {
                const parent = document.getElementById('id_consent_autorisation_parentale_declaree');
                if (parent && !parent.checked) return false;
            }
            return true;
        }

        if (step === 2) {
            const age = calculateAge();
            if (age !== null && age < 14) return false;
        }

        const requiredRadioNames = new Set(
            Array.from(pane.querySelectorAll('input[type="radio"][required]'))
                .filter((radio) => !radio.disabled)
                .map((radio) => radio.name),
        );
        for (const name of requiredRadioNames) {
            if (!pane.querySelector(`input[type="radio"][name="${name}"]:checked`)) {
                return false;
            }
        }

        const requiredInputs = pane.querySelectorAll('input[required]:not([type="radio"]), select[required], textarea[required]');
        for (const input of requiredInputs) {
            if (input.disabled) continue;
            if (input.type === 'file') {
                if (!input.files || input.files.length === 0) return false;
            } else if (!input.value) {
                return false;
            }
        }

        if (step === 5 && !autorisationBlock.classList.contains('d-none')) {
            const parentFile = document.getElementById('id_autorisation_parentale');
            if (parentFile && parentFile.files.length === 0) return false;
        }

        return true;
    }

    function findFirstIncompleteQuizGroup() {
        if (!quizPane) return null;
        const groups = new Map();
        quizPane.querySelectorAll('input[type="radio"]').forEach((radio) => {
            if (radio.disabled) return;
            if (!groups.has(radio.name)) {
                groups.set(radio.name, radio);
            }
        });
        for (const [name, sample] of groups.entries()) {
            if (!quizPane.querySelector(`input[type="radio"][name="${name}"]:checked`)) {
                return sample;
            }
        }
        return null;
    }

    function showToast(message, duration = 2500) {
        const toast = document.createElement('div');
        toast.className = 'alert alert-warning position-fixed top-0 end-0 m-3';
        toast.style.zIndex = '2000';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), duration);
    }

    function showIncompleteQuizTarget(radio) {
        if (!radio) return;
        const targetPane = radio.closest('.tab-pane');
        if (targetPane && targetPane.id) {
            const tabButton = document.querySelector(`#quizTabs button[data-bs-target="#${targetPane.id}"]`);
            if (tabButton) {
                bootstrap.Tab.getOrCreateInstance(tabButton).show();
            }
        }

        const quizCard = radio.closest('.quiz-question');
        if (quizCard) {
            quizCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function updateFinalStepActions() {
        if (currentStep !== panes.length) {
            nextBtn.classList.remove('d-none');
            submitBtn.classList.add('d-none');
            return;
        }

        const allAnswered = !findFirstIncompleteQuizGroup();
        nextBtn.classList.toggle('d-none', allAnswered);
        submitBtn.classList.toggle('d-none', !allAnswered);
    }

    function goToNextQuizTabOrIncomplete() {
        if (!quizTabButtons.length) return;
        const activeIndex = quizTabButtons.findIndex((btn) => btn.classList.contains('active'));
        if (activeIndex >= 0 && activeIndex < quizTabButtons.length - 1) {
            bootstrap.Tab.getOrCreateInstance(quizTabButtons[activeIndex + 1]).show();
            return;
        }

        const firstIncomplete = findFirstIncompleteQuizGroup();
        if (firstIncomplete) {
            showIncompleteQuizTarget(firstIncomplete);
        }
    }

    function showStep(step) {
        panes.forEach((pane) => {
            pane.classList.toggle('active', parseInt(pane.dataset.step, 10) === step);
        });

        currentStep = step;
        prevBtn.disabled = step === 1;
        const pct = Math.round((step / panes.length) * 100);
        progressBar.style.width = `${pct}%`;
        progressPercent.textContent = `${pct}%`;
        currentStepLabel.textContent = `${step}`;
        updateFinalStepActions();
        if (step === panes.length) {
            startQuizTimer();
        }
    }

    function startQuizTimer() {
        if (!timerEl) return;
        if (quizTimerInterval) return;
        quizTimerInterval = setInterval(() => {
            quizTimerSeconds += 1;
            const mm = String(Math.floor(quizTimerSeconds / 60)).padStart(2, '0');
            const ss = String(quizTimerSeconds % 60).padStart(2, '0');
            timerEl.textContent = `Temps indicatif : ${mm}:${ss}`;
        }, 1000);
    }

    restoreDraft();
    updateAcademicFieldsByLevel();
    updateEligibilityIndicators();
    updateScoreMeters();
    updateDocumentBadges();
    if (timerEl) {
        timerEl.textContent = 'Temps indicatif : 0:0';
    }
    showStep(1);
    nextBtn.addEventListener('click', () => {
        if (currentStep === panes.length) {
            const firstIncomplete = findFirstIncompleteQuizGroup();
            if (firstIncomplete) {
                goToNextQuizTabOrIncomplete();
                showToast('Complétez toutes les sections du quiz pour activer la soumission.', 2800);
            }
            return;
        }

        if (!validateStep(currentStep)) {
            showToast('Veuillez compléter correctement cette étape avant de continuer.');
            return;
        }
        saveDraft();
        showStep(Math.min(panes.length, currentStep + 1));
    });
    prevBtn.addEventListener('click', () => {
        showStep(Math.max(1, currentStep - 1));
    });

    form.addEventListener('input', () => {
        updateEligibilityIndicators();
        updateScoreMeters();
        updateFinalStepActions();
        saveDraft();
    });

    form.addEventListener('change', () => {
        updateAcademicFieldsByLevel();
        updateEligibilityIndicators();
        updateDocumentBadges();
        updateFinalStepActions();
        saveDraft();
    });

    form.addEventListener('submit', (event) => {
        const firstIncomplete = findFirstIncompleteQuizGroup();
        if (firstIncomplete) {
            event.preventDefault();
            showStep(6);
            showIncompleteQuizTarget(firstIncomplete);
            showToast('Veuillez repondre a toutes les questions du quiz avant de soumettre.', 3500);
            return;
        }
        sessionStorage.removeItem(STORAGE_KEY);
    });
})();

