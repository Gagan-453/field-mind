// bev_core.hpp -- the parts of bev-decider that are not the transformer:
// the token layout of one question, and the decision head. No llama.cpp
// dependency, so tests/test_bev_core.py builds and checks it on any host.
//
// Reproduces bev_decider 0.2.1 (Apache-2.0, github.com/avbiswas/bev-decider):
//   encode.py  Encoder.encode / question_options  -> bev::encode
//   model.py   ChoiceHead.forward                  -> bev::Head::forward
//
// How the layout becomes bev's attention mask on llama.cpp (bev_decide.cpp):
//   prompt   seq 0,     positions 0 .. P-1
//   option i seq i+1,   positions P .. P+len_i-1   (seq i+1 holds a copy of
//            the prompt's cells, so option i sees the prompt and itself only)
//   answer   seq N+1,   positions P+maxlen ..      (seq N+1 holds the prompt
//            and every option's cells, so the answer sees everything)
// A cell is visible to a token iff the cell carries the token's sequence and
// its position is not after the token's. That is encode.py's mask exactly.

#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <functional>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace bev {

using Tokens = std::vector<int32_t>;
using Tokenize = std::function<Tokens(const std::string &)>;
using Detokenize = std::function<std::string(const Tokens &)>;

// Encoding constants: bev_head.json (written by bench/bev_convert.py from encode.py).
struct EncodingConsts {
    std::map<std::string, std::string> task_prompts;   // choice / noul / score
    std::map<std::string, int> task_types;             // choice 0, noul 1, score 2
    std::string answer_prompt = "The answer is:";
    std::string option_begin = "<option>";
    std::string option_end = "</option>";
    int max_state_tokens = 2048;
    int max_choice_tokens = 64;
};

struct Question {
    std::string type;                   // choice | noul | score
    std::string instructions;
    // choice: (key, description) in request order; score: levels; noul: optional
    // {"false": .., "true": ..} given as two entries keyed "false" and "true".
    std::vector<std::pair<std::string, std::string>> criteria;
};

struct Layout {
    Tokens prompt;                      // seq 0
    std::vector<Tokens> options;        // option i -> seq i+1
    std::vector<int> read_idx;          // per option: index INSIDE options[i] read for its embedding
    Tokens answer;                      // seq N+1
    std::vector<std::string> keys;      // probability keys, in option order
    int task_type = 0;
    int P() const { return (int) prompt.size(); }
    int max_option_len() const {
        int m = 0;
        for (auto & o : options) m = std::max(m, (int) o.size());
        return m;
    }
    int answer_pos0() const { return options.empty() ? P() : P() + max_option_len(); }
    int n_tokens() const {
        int n = P() + (int) answer.size();
        for (auto & o : options) n += (int) o.size();
        return n;
    }
};

// encode.py Encoder.truncate: whole text if it fits, else decode(first max tokens).
inline std::string truncate(const std::string & text, int max_tokens,
                            const Tokenize & tok, const Detokenize & detok) {
    Tokens t = tok(text);
    if ((int) t.size() <= max_tokens) return text;
    return detok(Tokens(t.begin(), t.begin() + max_tokens));
}

// encode.py question_options (string criteria only; bev_decide.cpp refuses others).
inline void question_options(const Question & q, std::vector<std::string> & options,
                             std::vector<std::string> & keys) {
    options.clear();
    keys.clear();
    if (q.type == "choice") {
        if (q.criteria.empty()) throw std::invalid_argument("a choice question needs criteria");
        for (auto & kv : q.criteria) {
            keys.push_back(kv.first);
            options.push_back(kv.second.empty() ? kv.first : kv.first + ": " + kv.second);
        }
    } else if (q.type == "score") {
        if (q.criteria.empty()) throw std::invalid_argument("a score question needs criteria");
        for (size_t i = 0; i < q.criteria.size(); ++i) {
            keys.push_back(std::to_string(i));
            options.push_back(std::to_string(i) + ": " + q.criteria[i].second);
        }
    } else if (q.type == "noul") {
        keys = {"false", "true"};
        if (q.criteria.empty()) {
            options = {"No", "Yes"};
        } else {
            std::string f, t;
            bool hf = false, ht = false;
            for (auto & kv : q.criteria) {
                if (kv.first == "false") { f = kv.second; hf = true; }
                if (kv.first == "true") { t = kv.second; ht = true; }
            }
            if (!hf || !ht) throw std::invalid_argument("noul criteria need 'true' and 'false'");
            options = {"No: " + f, "Yes: " + t};
        }
    } else {
        throw std::invalid_argument("unknown question type '" + q.type + "'; expected choice, noul or score");
    }
}

inline Layout encode(const std::string & state, const Question & q, const EncodingConsts & c,
                     const Tokenize & tok, const Detokenize & detok) {
    auto tp = c.task_prompts.find(q.type);
    auto tt = c.task_types.find(q.type);
    if (tp == c.task_prompts.end() || tt == c.task_types.end())
        throw std::invalid_argument("unknown question type '" + q.type + "'");
    Layout L;
    L.task_type = tt->second;
    std::vector<std::string> options;
    question_options(q, options, L.keys);
    // The task hint and question come before the state (encode.py).
    std::string prompt = tp->second + "\nQuestion: " + q.instructions + "\n\n" +
                         truncate(state, c.max_state_tokens, tok, detok) + "\n";
    L.prompt = tok(prompt);
    Tokens ob = tok(c.option_begin), oe = tok(c.option_end);
    for (auto & o : options) {
        Tokens t = ob;
        Tokens body = tok(truncate(o, c.max_choice_tokens, tok, detok));
        t.insert(t.end(), body.begin(), body.end());
        t.insert(t.end(), oe.begin(), oe.end());
        // read at the last content token, before </option>
        L.read_idx.push_back((int) t.size() - 1 - (int) oe.size());
        L.options.push_back(std::move(t));
    }
    L.answer = tok(c.answer_prompt);
    return L;
}

// ---------------------------------------------------------------------------
// The decision head (model.py ChoiceHead), fp32 weights, double accumulation.

struct TensorSpec {
    std::string name;
    std::vector<int64_t> shape;
    int64_t offset = 0, nbytes = 0;
};

class Head {
  public:
    int H = 0, D = 0, n_layers = 0, n_tasks = 0;
    double eps = 1e-5;

    // bin: the whole bev_head.bin; specs: its manifest (bev_head.json "tensors").
    void load(const std::vector<float> & bin, const std::vector<TensorSpec> & specs,
              int hidden, int new_dim, int layers, int tasks, double layer_norm_eps) {
        H = hidden; D = new_dim; n_layers = layers; n_tasks = tasks; eps = layer_norm_eps;
        for (auto & s : specs) {
            int64_t n = 1;
            for (auto d : s.shape) n *= d;
            if (s.nbytes != n * 4 || s.offset % 4 || (s.offset + s.nbytes) / 4 > (int64_t) bin.size())
                throw std::runtime_error("head tensor " + s.name + ": bad offset or size");
            t_[s.name] = {bin.begin() + s.offset / 4, bin.begin() + (s.offset + s.nbytes) / 4};
            shape_[s.name] = s.shape;
        }
        need("task_embedding.weight", {tasks, H});
        for (const char * n : {"input_norm", "final_norm"}) {
            need(std::string(n) + ".weight", {H});
            need(std::string(n) + ".bias", {H});
        }
        for (const char * n : {"answer_proj", "choice_proj"}) {
            need(std::string(n) + ".weight", {D, H});
            need(std::string(n) + ".bias", {D});
        }
        for (int l = 0; l < layers; ++l) {
            std::string p = "layers." + std::to_string(l) + ".";
            for (const char * n : {"norm1", "norm2"}) {
                need(p + n + ".weight", {H});
                need(p + n + ".bias", {H});
            }
            for (const char * n : {"attn.q", "attn.k", "attn.v", "mlp.0"}) {
                need(p + n + ".weight", {D, H});
                need(p + n + ".bias", {D});
            }
            for (const char * n : {"attn.o", "mlp.2"}) {
                need(p + n + ".weight", {H, D});
                need(p + n + ".bias", {H});
            }
        }
    }

    // choices: C rows of H (the backbone's hidden state at each option's read
    // token); answer: H (at the last answer token). Returns softmax over C.
    std::vector<double> forward(const std::vector<std::vector<float>> & choices,
                                const std::vector<float> & answer, int task_type) const {
        const int C = (int) choices.size();
        if (C == 0) throw std::invalid_argument("no options");
        if (task_type < 0 || task_type >= n_tasks) throw std::invalid_argument("bad task type");
        using Vec = std::vector<double>;
        std::vector<Vec> x;
        const auto & te = t("task_embedding.weight");
        x.emplace_back(te.begin() + (size_t) task_type * H, te.begin() + (size_t) (task_type + 1) * H);
        for (auto & c : choices) {
            if ((int) c.size() != H) throw std::invalid_argument("choice embedding size");
            x.emplace_back(c.begin(), c.end());
        }
        if ((int) answer.size() != H) throw std::invalid_argument("answer embedding size");
        x.emplace_back(answer.begin(), answer.end());
        const int T = (int) x.size();          // 1 + C + 1, no padding: every slot attends to every slot

        for (auto & r : x) r = layer_norm(r, "input_norm");
        for (int l = 0; l < n_layers; ++l) {
            std::string p = "layers." + std::to_string(l) + ".";
            std::vector<Vec> h(T), q(T), k(T), v(T);
            for (int i = 0; i < T; ++i) {
                h[i] = layer_norm(x[i], p + "norm1");
                q[i] = linear(h[i], p + "attn.q");
                k[i] = linear(h[i], p + "attn.k");
                v[i] = linear(h[i], p + "attn.v");
            }
            const double scale = 1.0 / std::sqrt((double) D);
            for (int i = 0; i < T; ++i) {
                Vec s(T);
                for (int j = 0; j < T; ++j) s[j] = dot(q[i], k[j]) * scale;
                softmax(s);
                Vec a(D, 0.0);
                for (int j = 0; j < T; ++j)
                    for (int d = 0; d < D; ++d) a[d] += s[j] * v[j][d];
                Vec o = linear(a, p + "attn.o");
                for (int d = 0; d < H; ++d) x[i][d] += o[d];
            }
            for (int i = 0; i < T; ++i) {
                Vec m = linear(layer_norm(x[i], p + "norm2"), p + "mlp.0");
                for (auto & z : m) z = 0.5 * z * (1.0 + std::erf(z / std::sqrt(2.0)));   // nn.GELU()
                m = linear(m, p + "mlp.2");
                for (int d = 0; d < H; ++d) x[i][d] += m[d];
            }
        }
        for (auto & r : x) r = layer_norm(r, "final_norm");
        Vec a = linear(x[T - 1], "answer_proj");
        Vec logits(C);
        for (int i = 0; i < C; ++i) logits[i] = dot(a, linear(x[1 + i], "choice_proj")) / std::sqrt((double) D);
        softmax(logits);
        return logits;
    }

  private:
    std::map<std::string, std::vector<float>> t_;
    std::map<std::string, std::vector<int64_t>> shape_;

    const std::vector<float> & t(const std::string & n) const { return t_.at(n); }

    void need(const std::string & n, std::vector<int64_t> shape) const {
        auto it = shape_.find(n);
        if (it == shape_.end()) throw std::runtime_error("head tensor missing: " + n);
        if (it->second != shape) throw std::runtime_error("head tensor has the wrong shape: " + n);
    }

    static double dot(const std::vector<double> & a, const std::vector<double> & b) {
        double s = 0.0;
        for (size_t i = 0; i < a.size(); ++i) s += a[i] * b[i];
        return s;
    }

    static void softmax(std::vector<double> & s) {
        double m = s[0];
        for (double z : s) m = std::max(m, z);
        double sum = 0.0;
        for (double & z : s) { z = std::exp(z - m); sum += z; }
        for (double & z : s) z /= sum;
    }

    // nn.Linear: y = W x + b, W row-major [out, in]
    std::vector<double> linear(const std::vector<double> & in, const std::string & n) const {
        const auto & W = t(n + ".weight");
        const auto & b = t(n + ".bias");
        const size_t out = b.size(), nin = in.size();
        std::vector<double> y(out);
        for (size_t o = 0; o < out; ++o) {
            double s = b[o];
            const float * w = W.data() + o * nin;
            for (size_t i = 0; i < nin; ++i) s += (double) w[i] * in[i];
            y[o] = s;
        }
        return y;
    }

    // nn.LayerNorm: biased variance, eps inside the square root
    std::vector<double> layer_norm(const std::vector<double> & in, const std::string & n) const {
        const auto & w = t(n + ".weight");
        const auto & b = t(n + ".bias");
        double mean = 0.0, var = 0.0;
        for (double z : in) mean += z;
        mean /= (double) in.size();
        for (double z : in) var += (z - mean) * (z - mean);
        var /= (double) in.size();
        const double inv = 1.0 / std::sqrt(var + eps);
        std::vector<double> y(in.size());
        for (size_t i = 0; i < in.size(); ++i) y[i] = (in[i] - mean) * inv * w[i] + b[i];
        return y;
    }
};

}  // namespace bev
