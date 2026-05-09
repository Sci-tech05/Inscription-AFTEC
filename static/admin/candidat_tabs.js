(function () {
  const isCandidatForm = document.body.classList.contains('app-inscription') && document.body.classList.contains('model-candidat') && document.body.classList.contains('change-form');
  if (!isCandidatForm) return;

  const form = document.getElementById('candidat_form');
  if (!form) return;

  const profileFieldset = form.querySelector('fieldset.module');
  const inlineGroups = Array.from(form.querySelectorAll('.inline-group'));
  if (!profileFieldset || inlineGroups.length === 0) return;

  const tabContainer = document.createElement('div');
  tabContainer.className = 'aftec-admin-tabs';

  const sections = [];
  sections.push({ label: 'Profil', panel: profileFieldset });

  inlineGroups.forEach((group) => {
    const heading = group.querySelector('h2, h3');
    const label = heading ? heading.textContent.trim() : 'Section';
    const normalized = label.toLowerCase();
    if (normalized.includes('note')) sections.push({ label: 'Notes', panel: group });
    else if (normalized.includes('document')) sections.push({ label: 'Documents', panel: group });
    else if (normalized.includes('quiz')) sections.push({ label: 'Quiz', panel: group });
    else if (normalized.includes('décision') || normalized.includes('decision')) sections.push({ label: 'Décision', panel: group });
  });

  const orderedLabels = ['Profil', 'Notes', 'Documents', 'Quiz', 'Décision'];
  const unique = [];
  orderedLabels.forEach((label) => {
    const found = sections.find((item) => item.label === label);
    if (found) unique.push(found);
  });

  if (!unique.length) return;

  unique.forEach((section, index) => {
    section.panel.classList.add('aftec-admin-tab-panel');
    if (index !== 0) section.panel.classList.add('hidden');

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'aftec-admin-tab-btn' + (index === 0 ? ' active' : '');
    btn.textContent = section.label;
    btn.addEventListener('click', () => {
      unique.forEach((s) => s.panel.classList.add('hidden'));
      unique.forEach((_, i) => tabContainer.children[i].classList.remove('active'));
      section.panel.classList.remove('hidden');
      btn.classList.add('active');
    });
    tabContainer.appendChild(btn);
  });

  profileFieldset.parentNode.insertBefore(tabContainer, profileFieldset);
})();
