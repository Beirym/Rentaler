def getWorkTitle(work_id: int, capital_letter: bool=True, add_emoji: bool=False) -> str:
    "Returns a human-like view of work title."

    works_data = {
        1: {
            'title': 'Клининг',
            'emoji': '🧴',
        }
    }

    title = works_data[work_id]['title']
    if add_emoji:
        title = works_data[work_id]['emoji'] + ' ' + title
    if capital_letter is False:
        title = title.lower()

    return title