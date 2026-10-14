/**
 * Canonical meta fingerprint——瀏覽器（inspector preview.js）與 node 端
 * （executor、check script）共用的單一實作，含輸入正規化：遞迴鍵排序後
 * 序列化再雜湊，兩端對同一 meta 必得同值（插入序無關）。
 *
 * 帳本落盤前完成 canonical 化（outputs/prototype-reviews 無既存帳本檔，
 * 零遷移成本）；此後 fingerprint 演算法不得再變更，否則所有帳本假過期。
 */

export function canonicalize(value) {
  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }

  if (value !== null && typeof value === "object") {
    const sorted = {};

    for (const key of Object.keys(value).sort()) {
      sorted[key] = canonicalize(value[key]);
    }

    return sorted;
  }

  return value;
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

/** meta 指紋輸入固定為 components＋compositions 兩區塊。 */
export function computeFingerprint(metaLike) {
  let source = "";

  try {
    source = canonicalJson({
      components: metaLike?.components ?? null,
      compositions: metaLike?.compositions ?? null,
    });
  } catch (error) {
    source = "";
  }

  let hash = 5381;

  for (let index = 0; index < source.length; index += 1) {
    hash = ((hash << 5) + hash + source.charCodeAt(index)) >>> 0;
  }

  return `cfp-${hash.toString(16)}`;
}
