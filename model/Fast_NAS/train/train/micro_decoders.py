import torch
import torch.nn as nn
import torch.nn.functional as F
from .layer_factory import OPS, conv_bn_relu, conv3x3

OP_NAMES = [
    "conv1x1",
    "conv3x3",
    "sep_conv_3x3",
    "sep_conv_5x5",
    "global_average_pool",
    "conv3x3_dil3",
    "conv3x3_dil12",
    "sep_conv_3x3_dil3",
    "sep_conv_5x5_dil6",
    "skip_connect",
    "none",
]

def collect_all(feats, collect_indices):
    out = feats[collect_indices[0]]
    for i in range(1, len(collect_indices)):
        collect = feats[collect_indices[i]]
        if out.size()[2] > collect.size()[2]:
            collect = nn.Upsample(
                size=out.size()[2:], mode="bilinear", align_corners=False
            )(collect)
        elif collect.size()[2] > out.size()[2]:
            out = nn.Upsample(
                size=collect.size()[2:], mode="bilinear", align_corners=False
            )(out)
        out = torch.cat([out, collect], 1)
    return out

class AggregateCell(nn.Module):

    def __init__(self, size_1, size_2, agg_size, pre_transform=True):
        super(AggregateCell, self).__init__()
        self.pre_transform = pre_transform
        if self.pre_transform:
            self.branch_1 = conv_bn_relu(size_1, agg_size, 1, 1, 0)
            self.branch_2 = conv_bn_relu(size_2, agg_size, 1, 1, 0)

    def forward(self, x1, x2):
        if self.pre_transform:
            x1 = self.branch_1(x1)
            x2 = self.branch_2(x2)
        if x1.size()[2:] > x2.size()[2:]:
            x2 = nn.Upsample(size=x1.size()[2:], mode="bilinear")(x2)
        elif x1.size()[2:] < x2.size()[2:]:
            x1 = nn.Upsample(size=x2.size()[2:], mode="bilinear")(x1)
        return x1 + x2


class ContextualCell(nn.Module):

    def __init__(self, config, inp, repeats=1):
        super(ContextualCell, self).__init__()
        self._ops = nn.ModuleList()
        self._pos = []
        self._collect_inds = [0]
        self._pools = ["x"]
        for ind, op in enumerate(config):
            if ind == 0:
                pos = 0
                op_id = op
                self._collect_inds.remove(pos)
                op_name = OP_NAMES[op_id]

                self._ops.append(OPS[op_name](inp, inp, 1, True, repeats))
                self._pos.append(pos)
                self._collect_inds.append(ind + 1)
                self._pools.append("{}({})".format(op_name, self._pools[pos]))
            else:
                pos1, pos2, op_id1, op_id2 = op

                for (pos, op_id) in zip([pos1, pos2], [op_id1, op_id2]):
                    if pos in self._collect_inds:
                        self._collect_inds.remove(pos)
                    op_name = OP_NAMES[op_id]

                    self._ops.append(OPS[op_name](inp, inp, 1, True, repeats))
                    self._pos.append(pos)

                    self._pools.append("{}({})".format(op_name, self._pools[pos]))

                op_name = "sum"

                self._ops.append(
                    AggregateCell(
                        size_1=None, size_2=None, agg_size=inp, pre_transform=False
                    )
                )
                self._pos.append([ind * 3 - 1, ind * 3])
                self._collect_inds.append(ind * 3 + 1)
                self._pools.append(
                    "{}({},{})".format(
                        op_name, self._pools[ind * 3 - 1], self._pools[ind * 3]
                    )
                )

    def forward(self, x):
        feats = [x]
        for pos, op in zip(self._pos, self._ops):
            if isinstance(pos, list):
                assert  len(pos) == 2, "Two ops must be provided"
                feats.append(op(feats[pos[0]], feats[pos[1]]))
            else:
                feats.append(op(feats[pos]))
        out = 0
        for i in self._collect_inds:
            out += feats[i]
        return out

    def prettify(self):
        return  " + ".join(self._pools[i] for i in self._collect_inds)

class MergeCell(nn.Module):
    def __init__(self, ctx_config, conn, inps, agg_size, ctx_cell, repeats=1):
        super(MicroDecoder, self).__init__()
        self.index_1, self.index_2 = conn
        inp_1, inp_2 = inps
        self.op_1 = ctx_cell(ctx_config, inp_1, repeats=repeats)
        self.op_2 = ctx_cell(ctx_config, inp_2, repeats=repeats)
        self.agg = AggregateCell(inp_1, inp_2, agg_size)

    def forward(self, x1, x2):
        x1 = self.op_1(x1)
        x2 = self.op_1(x2)
        return self.agg(x1, x2)

    def prettify(self):
        return self.op_1.prettify()

class MicroDecoder(nn.Module):
    def __init__(
        self,
        inp_sizes,
        num_classes,
        config,
        agg_size=64,
        num_pools=4,
        ctx_cell=ContextualCell,
        aux_cell=False,
        repeats=1,
        **kwargs
    ):
        super(MicroDecoder, self).__init__()
        cells = []
        aux_clfs = []
        self.aux_cell = aux_cell
        self.collect_inds = []

        self.pool = ["l{}".format(i + 1) for i in range(num_pools)]
        self.info = []
        self.agg_size = agg_size

        for out_idx, size in enumerate(inp_sizes):
            setattr(
                self,
                "adapt{}".format(out_idx +1),
                conv_bn_relu(size, agg_size, 1, 1, 0, affine=True),
            )
            inp_sizes[out_idx] = agg_size

        inp_sizes = inp_sizes.copy()
        cell_config, conns = config
        self.conns = conns
        self.ctx = cell_config
        self.repeats = repeats
        self.collect_inds = []
        self.ctx_cell = ctx_cell
        for block_idx, conn in enumerate(conns):
            for ind in conn:
                if ind in self.collect_inds:

                    self.collect_inds.remove(ind)
            ind_1, ind_2 = conn
            cells.append(
                MergeCell(
                    cell_config,
                    conn,
                    (inp_sizes[ind_1], inp_sizes[ind_2]),
                    agg_size,
                    ctx_cell,
                    repeats=repeats,
                )
            )
            aux_clfs.append(nn.Sequential())
            if self.aux_cell:
                aux_clfs[block_idx].add_module(
                    "aux_clf", ctx_cell(self.ctx, agg_size, repeats=repeats)
                )
            aux_clfs[block_idx].add_module(
                "aux_clf", conv3x3(agg_size, num_classes, stride=1, bias=True)
            )
            self.collect_inds.append(block_idx + num_pools)
            inp_sizes.append(agg_size)

            self.pool.append("({} + {})".format(self.pool[ind_1], self.pool[ind_2]))
        self.cells = nn.ModuleList(cells)
        self.aux_clfs = nn.ModuleList(aux_clfs)
        self.pre_clf = conv_bn_relu(
            agg_size * len(self.collect_inds), agg_size, 1, 1, 0
        )
        self.conv_clf = conv3x3(agg_size, num_classes, stride=1, bias=True)
        self.info = " + ".join(self.pool[i] for i in self.collect_inds)
        self.num_classes = num_classes

    def prettify(self, n_params):

        header = "#PARAMS\n\n {:3.2f}M".format(n_params / 1e6)
        ctx_desc = "#Contextual:\n" + self.cells[0].prettify()
        conn_desc = "#Connections:\n" + self.info
        return header + "\n\n" + ctx_desc + "\n\n" +conn_desc

    def forward(self, x):
        x = list(x)
        aux_outs = []
        for out_idx in range(len(x)):
            x[out_idx] = getattr(self, "adapt{}".format(out_idx + 1))(x[out_idx])
        for cell, aux_clf, conn in zip(self.cells, self.aux_clfs, self.conns):
            cell_out = cell(x[conn[0]], x[conn[1]])
            x.append(cell_out)
            aux_outs.append(aux_clf(cell_out.clone()))
        out = collect_all(x, self.collect_inds)
        out = F.relu(out)
        out = self.pre_clf(out)
        out = self.conv_clf(out)
        return out, aux_outs