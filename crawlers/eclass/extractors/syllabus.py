"""강의 계획서 추출."""

from config import BASE_URL, GOTO_TIMEOUT_MS

_TEXTBOOK_KEYS = {"주교재", "부교재", "참고교재", "참고서적", "참고도서"}


async def extract_syllabus(page, course_id: int) -> dict:
    """강의 계획서 페이지에서 데이터를 추출한다."""
    url = f"{BASE_URL}/local/ubion/setting/syllabus.php?id={course_id}"
    await page.goto(url, wait_until="networkidle", timeout=GOTO_TIMEOUT_MS)

    data = await page.evaluate("""
        () => {
            const result = {};
            const textbookKeys = new Set(['주교재', '부교재', '참고교재', '참고서적', '참고도서']);
            const textbooks = [];

            // 테이블 기반 강의계획서
            document.querySelectorAll('table tr, .syllabus-table tr').forEach(tr => {
                const th = tr.querySelector('th, td:first-child');
                const td = tr.querySelector('td:last-child, td:nth-child(2)');
                if (th && td && th !== td) {
                    const key = th.innerText.trim();
                    const value = td.innerText.trim();
                    if (!key || !value) return;

                    if (textbookKeys.has(key)) {
                        // 교재: 셀 안에 줄바꿈/리스트로 여러 권이 있을 수 있음
                        const items = td.querySelectorAll('li');
                        if (items.length > 0) {
                            items.forEach(li => {
                                const t = li.innerText.trim();
                                if (t) textbooks.push({type: key, title: t});
                            });
                        } else {
                            value.split('\\n').forEach(line => {
                                const t = line.trim();
                                if (t) textbooks.push({type: key, title: t});
                            });
                        }
                        result[key] = value;
                    } else {
                        result[key] = value;
                    }
                }
            });

            // div 기반 레이아웃도 시도
            if (Object.keys(result).length === 0) {
                document.querySelectorAll('.form-group, .fitem, [class*="syllabus"]').forEach(el => {
                    const label = el.querySelector('label, .col-form-label, dt, .label');
                    const value = el.querySelector('.form-control-static, dd, .value, .felement');
                    if (label && value) {
                        const key = label.innerText.trim();
                        const val = value.innerText.trim();
                        if (textbookKeys.has(key) && val) {
                            const items = value.querySelectorAll('li');
                            if (items.length > 0) {
                                items.forEach(li => {
                                    const t = li.innerText.trim();
                                    if (t) textbooks.push({type: key, title: t});
                                });
                            } else {
                                val.split('\\n').forEach(line => {
                                    const t = line.trim();
                                    if (t) textbooks.push({type: key, title: t});
                                });
                            }
                        }
                        result[key] = val;
                    }
                });
            }

            // 교재 전용 영역 탐색 (별도 섹션/리스트)
            document.querySelectorAll('ul, ol').forEach(list => {
                const prev = list.previousElementSibling;
                if (prev) {
                    const header = prev.innerText.trim();
                    if (textbookKeys.has(header) || header.includes('교재') || header.includes('참고')) {
                        const ttype = textbookKeys.has(header) ? header : '참고교재';
                        list.querySelectorAll('li').forEach(li => {
                            const t = li.innerText.trim();
                            if (t) textbooks.push({type: ttype, title: t});
                        });
                    }
                }
            });

            if (textbooks.length > 0) {
                result['_textbooks'] = textbooks;
            }

            // 전체 텍스트 백업
            if (Object.keys(result).length === 0) {
                const main = document.querySelector('#region-main, .course-content, main');
                if (main) {
                    result['_raw_text'] = main.innerText.trim().substring(0, 5000);
                }
            }

            return result;
        }
    """)

    field_count = len([k for k in data if not k.startswith('_')])
    textbook_count = len(data.get('_textbooks', []))
    print(f"  [SYLLABUS] course={course_id}: {field_count}개 항목, 교재 {textbook_count}권 추출")
    return data
