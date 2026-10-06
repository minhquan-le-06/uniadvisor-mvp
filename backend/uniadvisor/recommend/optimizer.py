"""Choose and order the application list to maximise expected utility.

    E = sum_i p_i * prod_{j before i} (1 - p_j) * u_i

In Vietnam a student is admitted to the highest-ranked wish whose cutoff they pass, and each p_i does
not depend on the order. Swapping two neighbours i, j changes E by p_i p_j (u_i - u_j), so for a fixed
set the best order is by utility, descending. What remains is *which* programs to include: an exact
dynamic programme over the utility-sorted candidates, with KB constraints (max number of wishes,
at least N 'safe' wishes, at most M wishes per school).

Assumes the p_i are independent given the student's score (cutoff errors differ per program); the
student's own score uncertainty makes them positively correlated, so P(admitted somewhere) is an
optimistic upper estimate when the score is a mock-exam estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Item:
    key: str
    p: float        # admission probability
    u: float        # utility in [0, 1]
    safe: bool
    school: str


def expected_value(items: list[Item]) -> float:
    e, miss = 0.0, 1.0
    for it in items:
        e += miss * it.p * it.u
        miss *= 1 - it.p
    return e


def p_any(items: list[Item]) -> float:
    return 1.0 - float(np.prod([1 - it.p for it in items])) if items else 0.0

def p_any_monte_carlo(
    chosen_evals: list[dict],
    student_sd: float = 0.0,
    n_sims: int = 5000,
    seed: int = 42,
) -> tuple[float, float]:
  """Mô phỏng Monte Carlo tính P(đỗ ít nhất 1 NV) và Kỳ vọng hữu dụng thực tế,

  giải quyết tương quan điểm thi dùng chung giữa các nguyện vọng khi thi thử.
  Trả về: (p_any_mc, expected_value_mc)
  """
  if not chosen_evals:
    return 0.0, 0.0

  # Nếu là điểm thi chính thức (không có sai số thí sinh), dùng công thức tất định độc lập
  if student_sd <= 0.0:
    items = [
        Item(
            ev["program"]["program_id"],
            ev["p_admit"],
            ev["utility"],
            ev["bucket"] == "safe",
            ev["program"]["school_code"],
        )
        for ev in chosen_evals
    ]
    return p_any(items), expected_value(items)

  rng = np.random.default_rng(seed)
  k = len(chosen_evals)

  # 1. Sinh ngẫu nhiên biến động điểm thi thật của thí sinh trên 5000 kịch bản
  # Sử dụng Student-t với df=4.0 khớp với độ dày đuôi phong độ thi cử
  delta_student = rng.standard_t(df=4.0, size=n_sims) * student_sd  # (n_sims,)

  # 2. Sinh điểm chuẩn thực tế và kiểm tra trúng tuyển cho từng nguyện vọng
  # passed_matrix[i, s] = True nếu thí sinh đỗ NV i trong kịch bản s
  passed_matrix = np.zeros((k, n_sims), dtype=bool)
  utilities = np.array([ev["utility"] for ev in chosen_evals], dtype=float)

  for i, ev in enumerate(chosen_evals):
    fc = ev["forecast"]
    # Điểm xét tuyển của thí sinh tại kịch bản s (bao gồm điểm ưu tiên và sai số thi cử)
    sim_student_total = ev["total"] + delta_student

    # Điểm chuẩn thực tế của trường i tại kịch bản s
    sim_cutoff_noise = rng.standard_t(df=fc.df, size=n_sims) * fc.sigma
    sim_actual_cutoff = fc.score + sim_cutoff_noise

    passed_matrix[i, :] = sim_student_total >= sim_actual_cutoff

  # 3. Xét tuyển từ trên xuống dưới theo thứ tự nguyện vọng 1 -> k
  # Thí sinh đỗ nguyện vọng cao nhất mà mình đủ điểm
  any_passed = np.any(passed_matrix, axis=0)  # shape (n_sims,)
  p_any_mc = float(np.mean(any_passed))

  # Tính kỳ vọng hữu dụng: lấy utility của nguyện vọng trúng tuyển đầu tiên
  sim_utility = np.zeros(n_sims, dtype=float)
  for s in range(n_sims):
    passed_indices = np.where(passed_matrix[:, s])[0]
    if len(passed_indices) > 0:
      first_choice = passed_indices[0]  # NV trúng tuyển đầu tiên
      sim_utility[s] = utilities[first_choice]

  ev_mc = float(np.mean(sim_utility))
  return round(p_any_mc, 4), round(ev_mc, 4)


def _dp(items: list[Item], k_max: int, min_safe: int) -> list[Item]:
    n = len(items)
    NEG = -1e9
    # g[i][k][r]: best E from items[i:] using at most k slots while r more safe items are required
    g = np.full((n + 1, k_max + 1, min_safe + 1), NEG)
    g[n, :, 0] = 0.0
    take = np.zeros((n, k_max + 1, min_safe + 1), dtype=bool)
    for i in range(n - 1, -1, -1):
        it = items[i]
        for k in range(k_max + 1):
            for r in range(min_safe + 1):
                best = g[i + 1, k, r]
                if k >= 1:
                    r2 = max(0, r - (1 if it.safe else 0))
                    rest = g[i + 1, k - 1, r2]
                    if rest > NEG / 2:
                        val = it.p * it.u + (1 - it.p) * rest
                        if val > best + 1e-12:
                            best = val
                            take[i, k, r] = True
                g[i, k, r] = best
    chosen, k, r = [], k_max, min_safe
    if g[0, k, r] <= NEG / 2:  # constraint infeasible (not enough safe options): relax it
        return _dp(items, k_max, max(0, min_safe - 1)) if min_safe > 0 else []
    for i in range(n):
        if k >= 1 and take[i, k, r]:
            chosen.append(items[i])
            r = max(0, r - (1 if items[i].safe else 0))
            k -= 1
    return chosen


# def optimise(candidates: list[Item], k_max: int = 10, min_safe: int = 2, max_per_school: int = 4) -> list[Item]:
#     items = sorted(candidates, key=lambda it: (-it.u, -it.p, it.key))
#     banned: set[str] = set()
#     for _ in range(50):
#         chosen = _dp([it for it in items if it.key not in banned], k_max, min_safe)
#         per_school: dict[str, list[Item]] = {}
#         for it in chosen:
#             per_school.setdefault(it.school, []).append(it)
#         over = [sorted(v, key=lambda it: it.p * it.u)[0] for v in per_school.values() if len(v) > max_per_school]
#         if not over:
#             return chosen
#         banned |= {it.key for it in over}
#     return chosen


def _beam_search_optimise(
    items: list[Item],
    k_max: int = 10,
    min_safe: int = 2,
    max_per_school: int = 4,
    beam_width: int = 100,
) -> list[Item]:
  """Constrained Beam Search: Tìm danh sách tối ưu thỏa mãn đồng thời

  k_max, min_safe và max_per_school trong đúng 1 lượt quét O(B * n).
  """
  # Trạng thái trong chùm: (expected_utility, miss_prob, safe_count, school_counts, chosen_items, last_idx)
  # Khởi tạo trạng thái rỗng
  beam = [(0.0, 1.0, 0, {}, [], -1)]
  n = len(items)

  for step in range(k_max):
    candidates_pool = []
    for exp_val, miss, safe_cnt, school_counts, chosen, last_idx in beam:
      # Duyệt các ứng viên tiếp theo (duy trì thứ tự utility giảm dần)
      for i in range(last_idx + 1, n):
        it = items[i]
        curr_school_cnt = school_counts.get(it.school, 0)
        if curr_school_cnt >= max_per_school:
          continue  # Ràng buộc cứng: không vượt quá max_per_school

        new_miss = miss * (1.0 - it.p)
        new_exp = exp_val + miss * it.p * it.u
        new_safe = safe_cnt + (1 if it.safe else 0)
        new_counts = dict(school_counts)
        new_counts[it.school] = curr_school_cnt + 1

        candidates_pool.append(
            (new_exp, new_miss, new_safe, new_counts, chosen + [it], i)
        )

    if not candidates_pool:
      break

    # Giữ lại top B trạng thái có kỳ vọng hữu dụng cao nhất
    candidates_pool.sort(key=lambda s: s[0], reverse=True)
    beam = candidates_pool[:beam_width]

  # Lọc trong beam trạng thái thỏa mãn điều kiện min_safe
  valid_states = [s for s in beam if s[2] >= min_safe]
  if valid_states:
    return valid_states[0][4]

  # Nếu không đủ min_safe, trả về trạng thái có expected utility cao nhất trong beam
  return beam[0][4] if beam else []


def optimise(
    candidates: list[Item],
    k_max: int = 10,
    min_safe: int = 2,
    max_per_school: int = 4,
) -> list[Item]:
  """Tối ưu hóa danh mục: Kết hợp DP chính xác và Constrained Beam Search fallback."""
  items = sorted(candidates, key=lambda it: (-it.u, -it.p, it.key))

  # 1. Chạy DP 1 lần duy nhất
  chosen = _dp(items, k_max, min_safe)

  # 2. Kiểm tra xem có trường nào vượt ngưỡng max_per_school không
  per_school: dict[str, int] = {}
  violated = False
  for it in chosen:
    per_school[it.school] = per_school.get(it.school, 0) + 1
    if per_school[it.school] > max_per_school:
      violated = True
      break

  # Nếu không vi phạm, trả về kết quả tối ưu tuyệt đối của DP
  if not violated:
    return chosen

  # 3. Nếu vi phạm, chuyển sang Constrained Beam Search giải quyết dứt điểm trong 1 lượt
  return _beam_search_optimise(
      items,
      k_max=k_max,
      min_safe=min_safe,
      max_per_school=max_per_school,
      beam_width=100,
  )