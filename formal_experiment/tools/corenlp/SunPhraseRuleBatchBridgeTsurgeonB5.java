import edu.stanford.nlp.trees.Tree;
import edu.stanford.nlp.trees.tregex.TregexMatcher;
import edu.stanford.nlp.trees.tregex.TregexPattern;
import edu.stanford.nlp.trees.tregex.tsurgeon.Tsurgeon;
import edu.stanford.nlp.trees.tregex.tsurgeon.TsurgeonPattern;

import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * B5 genuine Tsurgeon bridge.
 *
 * Hypothesis (must not be overstated):
 * - Bridge still emits condition/constraint/exception matches from the
 *   pre-surgery tree (Sun order: match then prune context).
 * - Tsurgeon's direct goal is to stop context content from polluting later
 *   action/actor extraction on the same working tree.
 * - Primary attributable targets are actor/action and overall precision;
 *   constraint metrics are side-effect observations only.
 *
 * Safety:
 * - Record original-token identity before surgery.
 * - If surgery returns null, empties all leaves, or would remove the full tree:
 *   restore the pre-surgery tree, emit surgery_rejected, never report
 *   operation_applied=true for rejected surgery.
 * - After surgery, surviving leaves may be discontinuous in original-token
 *   space; emit contiguous original-token runs (e.g. 3-7,12-16), never a
 *   min..max envelope that re-includes pruned gaps.
 */
public final class SunPhraseRuleBatchBridgeTsurgeonB5 {
  private static final class Rule {
    final String field;
    final TregexPattern pattern;
    final TsurgeonPattern operation;
    final boolean surgeryEnabled;

    Rule(String field, TregexPattern pattern, TsurgeonPattern operation, boolean surgeryEnabled) {
      this.field = field;
      this.pattern = pattern;
      this.operation = operation;
      this.surgeryEnabled = surgeryEnabled;
    }
  }

  private static final class Snapshot {
    final Tree tree;
    final IdentityHashMap<Tree, Integer> originalLeafIndexes;

    Snapshot(Tree tree, IdentityHashMap<Tree, Integer> originalLeafIndexes) {
      this.tree = tree;
      this.originalLeafIndexes = originalLeafIndexes;
    }
  }

  private SunPhraseRuleBatchBridgeTsurgeonB5() {}

  private static List<Rule> loadRules(Path planPath) throws Exception {
    List<Rule> rules = new ArrayList<>();
    for (String raw : Files.readAllLines(planPath, StandardCharsets.UTF_8)) {
      if (raw.trim().isEmpty() || raw.startsWith("#")) {
        continue;
      }
      String[] parts = raw.split("\t", -1);
      if (parts.length != 3 || parts[0].trim().isEmpty() || parts[1].trim().isEmpty()) {
        throw new IllegalArgumentException("invalid rule-plan line: " + raw);
      }
      String opText = parts[2] == null ? "" : parts[2].trim();
      boolean enabled = !opText.isEmpty();
      TsurgeonPattern operation = enabled ? Tsurgeon.parseOperation(opText) : null;
      rules.add(new Rule(parts[0], TregexPattern.compile(parts[1]), operation, enabled));
    }
    if (rules.isEmpty()) {
      throw new IllegalArgumentException("rule plan is empty");
    }
    return rules;
  }

  private static Map<String, List<Rule>> groupRules(List<Rule> rules) {
    Map<String, List<Rule>> grouped = new LinkedHashMap<>();
    for (Rule rule : rules) {
      grouped.computeIfAbsent(rule.field, ignored -> new ArrayList<>()).add(rule);
    }
    return grouped;
  }

  private static String nodeText(Tree node) {
    List<String> words = new ArrayList<>();
    for (Tree leaf : node.getLeaves()) {
      words.add(leaf.label().value());
    }
    return String.join(" ", words).replace('\t', ' ').replace('\n', ' ');
  }

  private static int[] originalSpanEnvelope(Tree node, IdentityHashMap<Tree, Integer> originalLeafIndexes) {
    int begin = Integer.MAX_VALUE;
    int end = -1;
    for (Tree leaf : node.getLeaves()) {
      Integer index = originalLeafIndexes.get(leaf);
      if (index == null) {
        throw new IllegalStateException("matched leaf lost its original index");
      }
      begin = Math.min(begin, index);
      end = Math.max(end, index + 1);
    }
    if (end < 0) {
      throw new IllegalStateException("matched node has no leaves");
    }
    return new int[] {begin, end};
  }

  /** Contiguous original-token runs for surviving leaves (no gap envelope). */
  private static String originalTokenRuns(Tree node, IdentityHashMap<Tree, Integer> originalLeafIndexes) {
    List<Integer> indexes = new ArrayList<>();
    for (Tree leaf : node.getLeaves()) {
      Integer index = originalLeafIndexes.get(leaf);
      if (index == null) {
        throw new IllegalStateException("matched leaf lost its original index");
      }
      indexes.add(index);
    }
    if (indexes.isEmpty()) {
      return "";
    }
    java.util.Collections.sort(indexes);
    StringBuilder sb = new StringBuilder();
    int runStart = indexes.get(0);
    int prev = indexes.get(0);
    for (int i = 1; i < indexes.size(); i++) {
      int cur = indexes.get(i);
      if (cur == prev) {
        continue;
      }
      if (cur == prev + 1) {
        prev = cur;
        continue;
      }
      if (sb.length() > 0) {
        sb.append(',');
      }
      sb.append(runStart).append('-').append(prev + 1);
      runStart = cur;
      prev = cur;
    }
    if (sb.length() > 0) {
      sb.append(',');
    }
    sb.append(runStart).append('-').append(prev + 1);
    return sb.toString();
  }

  private static boolean overlaps(int begin, int end, List<int[]> taken) {
    for (int[] span : taken) {
      if (begin < span[1] && end > span[0]) {
        return true;
      }
    }
    return false;
  }

  private static int leafCount(Tree tree) {
    if (tree == null) {
      return 0;
    }
    return tree.getLeaves().size();
  }

  /** Copy a working tree while carrying each surviving leaf's original token id. */
  private static Snapshot snapshot(
      Tree tree, IdentityHashMap<Tree, Integer> originalLeafIndexes) {
    Tree copy = tree.deepCopy();
    List<Tree> sourceLeaves = tree.getLeaves();
    List<Tree> copyLeaves = copy.getLeaves();
    if (sourceLeaves.size() != copyLeaves.size()) {
      throw new IllegalStateException("tree snapshot changed leaf count");
    }
    IdentityHashMap<Tree, Integer> copiedIndexes = new IdentityHashMap<>();
    for (int i = 0; i < sourceLeaves.size(); i++) {
      Integer originalIndex = originalLeafIndexes.get(sourceLeaves.get(i));
      if (originalIndex == null) {
        throw new IllegalStateException("working leaf lost original token identity");
      }
      copiedIndexes.put(copyLeaves.get(i), originalIndex);
    }
    return new Snapshot(copy, copiedIndexes);
  }

  private static boolean everyLeafHasOriginalIdentity(
      Tree tree, IdentityHashMap<Tree, Integer> originalLeafIndexes) {
    for (Tree leaf : tree.getLeaves()) {
      if (!originalLeafIndexes.containsKey(leaf)) {
        return false;
      }
    }
    return true;
  }

  public static void main(String[] args) throws Exception {
    // Windows console code pages must not alter bridge evidence bytes.  The
    // Python caller always decodes stdout as UTF-8.
    System.setOut(new PrintStream(System.out, true, "UTF-8"));
    System.setErr(new PrintStream(System.err, true, "UTF-8"));
    if (args.length != 2) {
      throw new IllegalArgumentException(
          "usage: SunPhraseRuleBatchBridgeTsurgeonB5 <rule-plan.tsv> <trees.txt>");
    }
    List<Rule> rules = loadRules(Paths.get(args[0]));
    Map<String, List<Rule>> grouped = groupRules(rules);
    List<String> trees = Files.readAllLines(Paths.get(args[1]), StandardCharsets.UTF_8);

    int treeCount = 0;
    int matchCount = 0;
    int surgeryAttempted = 0;
    int surgeryAccepted = 0;
    int surgeryRejected = 0;
    int terminalTreeRemovalCount = 0;
    int sourceSliceFailureCount = 0;
    Map<String, Integer> perFieldSurgeryAttempted = new LinkedHashMap<>();
    Map<String, Integer> perFieldSurgeryAccepted = new LinkedHashMap<>();
    Map<String, Integer> perFieldSurgeryRejected = new LinkedHashMap<>();
    Map<String, Integer> perFieldMatch = new LinkedHashMap<>();
    int postSurgeryActionMatches = 0;
    int postSurgeryActorMatches = 0;
    for (String field : grouped.keySet()) {
      perFieldSurgeryAttempted.put(field, 0);
      perFieldSurgeryAccepted.put(field, 0);
      perFieldSurgeryRejected.put(field, 0);
      perFieldMatch.put(field, 0);
    }

    for (String rawTree : trees) {
      if (rawTree.trim().isEmpty()) {
        continue;
      }
      Tree working = Tree.valueOf(rawTree);
      if (working == null) {
        throw new IllegalStateException("failed to parse tree at index " + treeCount);
      }
      IdentityHashMap<Tree, Integer> leafIndexes = new IdentityHashMap<>();
      List<Tree> originalLeaves = working.getLeaves();
      for (int index = 0; index < originalLeaves.size(); index++) {
        leafIndexes.put(originalLeaves.get(index), index);
      }
      for (Map.Entry<String, List<Rule>> fieldRules : grouped.entrySet()) {
        String field = fieldRules.getKey();
        if (working == null || leafCount(working) == 0) {
          System.out.printf("MISS\t%d\t%s%n", treeCount, field);
          continue;
        }
        List<int[]> taken = new ArrayList<>();
        boolean anyMatch = false;
        boolean progressed = true;
        while (progressed && working != null && leafCount(working) > 0) {
          progressed = false;
          int patternIndex = 0;
          for (Rule rule : fieldRules.getValue()) {
            TregexMatcher matcher = rule.pattern.matcher(working);
            Tree named = null;
            int[] span = null;
            String runs = null;
            while (matcher.find()) {
              Tree candidate = matcher.getNode(field);
              if (candidate == null) {
                throw new IllegalStateException(
                    "pattern matched but did not bind node name " + field);
              }
              int[] candidateSpan = originalSpanEnvelope(candidate, leafIndexes);
              if (overlaps(candidateSpan[0], candidateSpan[1], taken)) {
                continue;
              }
              named = candidate;
              span = candidateSpan;
              runs = originalTokenRuns(candidate, leafIndexes);
              break;
            }
            if (named == null) {
              patternIndex++;
              continue;
            }

            boolean phasePostSurgery = "action".equals(field) || "actor".equals(field);
            String phase = phasePostSurgery ? "post_surgery" : "pre_surgery";
            boolean operationApplied = false;
            String surgeryStatus = "none";
            String matchedText = nodeText(named);

            if (rule.surgeryEnabled && rule.operation != null) {
              surgeryAttempted++;
              perFieldSurgeryAttempted.put(
                  field, perFieldSurgeryAttempted.get(field) + 1);
              // The snapshot records original-token identity immediately before
              // every destructive attempt and is the exact rollback state.
              Snapshot before = snapshot(working, leafIndexes);
              Tree after = null;
              boolean accepted = false;
              try {
                after = Tsurgeon.processPattern(rule.pattern, rule.operation, working);
                if (after == null) {
                  surgeryStatus = "rejected_null";
                  terminalTreeRemovalCount++;
                } else if (leafCount(after) == 0) {
                  surgeryStatus = "rejected_empty_leaves";
                  terminalTreeRemovalCount++;
                } else if (!everyLeafHasOriginalIdentity(after, leafIndexes)) {
                  surgeryStatus = "rejected_original_identity_drift";
                  sourceSliceFailureCount++;
                } else if (after.toString().equals(before.tree.toString())) {
                  surgeryStatus = "rejected_no_change";
                } else {
                  accepted = true;
                }
              } catch (RuntimeException ex) {
                surgeryStatus = "rejected_exception";
                after = null;
              }
              if (accepted) {
                working = after;
                surgeryAccepted++;
                operationApplied = true;
                surgeryStatus = "accepted";
                perFieldSurgeryAccepted.put(field, perFieldSurgeryAccepted.get(field) + 1);
              } else {
                working = before.tree;
                leafIndexes = before.originalLeafIndexes;
                surgeryRejected++;
                perFieldSurgeryRejected.put(
                    field, perFieldSurgeryRejected.get(field) + 1);
                operationApplied = false;
                if ("none".equals(surgeryStatus) || surgeryStatus.startsWith("rejected") == false) {
                  surgeryStatus = "rejected_restore";
                }
              }
            }

            System.out.printf(
                "MATCH\t%d\t%s\t%d\t%d\t%s\t%d\t%s\t%s\t%s\t%s%n",
                treeCount,
                field,
                span[0],
                span[1],
                matchedText,
                patternIndex,
                operationApplied ? "true" : "false",
                phase,
                surgeryStatus,
                runs == null ? "" : runs);
            matchCount++;
            perFieldMatch.put(field, perFieldMatch.get(field) + 1);
            if ("action".equals(field)) {
              postSurgeryActionMatches++;
            }
            if ("actor".equals(field)) {
              postSurgeryActorMatches++;
            }
            anyMatch = true;
            taken.add(span);
            progressed = true;
            break;
          }
        }
        if (!anyMatch) {
          System.out.printf("MISS\t%d\t%s%n", treeCount, field);
        }
      }

      System.out.printf(
          "FINAL\t%d\t%s%n",
          treeCount,
          working == null || leafCount(working) == 0
              ? "<TREE_REMOVED>"
              : working.toString().replace('\t', ' ').replace('\n', ' '));
      treeCount++;
    }

    // Fail closed if any terminal removal was counted as accepted (must be 0 accepted full removals).
    System.out.printf("RAW_MATCH_COUNT\t%d%n", matchCount);
    System.out.printf("TERMINAL_TREE_REMOVALS\t%d%n", terminalTreeRemovalCount);
    System.out.printf("SURGERY_ATTEMPTED\t%d%n", surgeryAttempted);
    System.out.printf("SURGERY_ACCEPTED\t%d%n", surgeryAccepted);
    System.out.printf("SURGERY_REJECTED\t%d%n", surgeryRejected);
    System.out.printf("SOURCE_SLICE_FAILURES\t%d%n", sourceSliceFailureCount);
    System.out.printf("POST_SURGERY_ACTION_MATCHES\t%d%n", postSurgeryActionMatches);
    System.out.printf("POST_SURGERY_ACTOR_MATCHES\t%d%n", postSurgeryActorMatches);
    for (Map.Entry<String, Integer> e : perFieldSurgeryAttempted.entrySet()) {
      System.out.printf("FIELD_SURGERY_ATTEMPTED\t%s\t%d%n", e.getKey(), e.getValue());
    }
    for (Map.Entry<String, Integer> e : perFieldSurgeryAccepted.entrySet()) {
      System.out.printf("FIELD_SURGERY_ACCEPTED\t%s\t%d%n", e.getKey(), e.getValue());
    }
    for (Map.Entry<String, Integer> e : perFieldSurgeryRejected.entrySet()) {
      System.out.printf("FIELD_SURGERY_REJECTED\t%s\t%d%n", e.getKey(), e.getValue());
    }
    for (Map.Entry<String, Integer> e : perFieldMatch.entrySet()) {
      System.out.printf("FIELD_MATCH\t%s\t%d%n", e.getKey(), e.getValue());
    }
    // SUMMARY: tree_count, pattern_count, match_count, surgery_accepted
    System.out.printf(
        "SUMMARY\t%d\t%d\t%d\t%d%n", treeCount, rules.size(), matchCount, surgeryAccepted);
  }
}
