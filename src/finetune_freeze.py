from utils import *

def tune(train_loader, model, criterion, optimizer, epoch, device, args, step_history):
    batch_time = AverageMeter('Time', ':6.3f')
    data_time = AverageMeter('Data', ':6.3f')
    losses = AverageMeter('Loss', ':.4e')
    top1 = AverageMeter('Acc@1', ':6.2f')
    top5 = AverageMeter('Acc@5', ':6.2f')
    progress = ProgressMeter(
        len(train_loader),
        [batch_time, data_time, losses, top1, top5],
        prefix="Epoch: [{}]".format(epoch))

    # switch to train mode
    model.train()

    end = time.time()
    for i, (images, target) in enumerate(train_loader):
        # measure data loading time
        data_time.update(time.time() - end)

        # move data to the same device as model
        images = images.to(device, non_blocking=True)
        target = target.to(device, non_blocking=True)

        # compute output
        output = model(images)
        loss = criterion(output, target)

        # measure accuracy and record loss
        acc1, acc5 = accuracy(output, target, topk=(1, 5))
        losses.update(loss.item(), images.size(0))
        top1.update(acc1[0], images.size(0))
        top5.update(acc5[0], images.size(0))

        optimizer.zero_grad()
        loss.backward()

        temp_model = copy.deepcopy(model)
        optimizer.step()


        for history in reversed(step_history[0]):
                for pruned_layer_name, b, channels_removed in reversed(history):
                    # loop through the layers of the larger model (same number of layers, different channel width)
                    for layer_name, tuning_params in model.named_parameters():

                        skipped = 0

                        if "module."+layer_name == pruned_layer_name + ".weight":

                            temp_layer = get_module_by_name(temp_model, layer_name[:-7])
                            bigger_layer = get_module_by_name(model, layer_name[:-7])

                            # loop throught the channels of the bigger model
                            for idx in range(bigger_layer.out_channels):

                                # check if the channel has been dropped
                                if idx in channels_removed:
                                    # if channel was dropped, do not copy weights, use updated weights

                                    skipped += 1

                                else:

                                    # the non pruned channels are not updated, and copied back from the temp weights before weight updates
                                    if "layer" not in layer_name:

                                        # tuning_params.requires_grad_(False)
                                        # the non pruned channels are not updated, and copied back from the temp weights
                                        #                         # before weight updates
                                        tuning_params.data[idx, :, :, :] = temp_layer.weight.data[idx - skipped, :, :, :]

                                    else:  # for conv layers with reshape of both input and output

                                        # tuning_params.requires_grad_(False)
                                        skipped_j = 0

                                        if (bigger_layer.in_channels - temp_layer.in_channels) == len(channels_removed):

                                            for idx_j in range(bigger_layer.in_channels):

                                                if idx_j in channels_removed:
                                                    # if channel was dropped, do not copy weights from smaller tuned model
                                                    skipped_j += 1
                                                else:
                                                    tuning_params.data[idx, idx_j, :, :] = temp_layer.weight.data[idx - skipped, idx_j - skipped_j, :, :]

        # measure elapsed time
        batch_time.update(time.time() - end)
        end = time.time()

        if i % args.print_freq == 0:
            progress.display(i + 1)